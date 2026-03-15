// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package usecase

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"

	sdkentities "geti.com/iai_core/entities"
	"geti.com/iai_core/frames"
	"geti.com/iai_core/logger"
	"geti.com/iai_core/storage"
	"geti.com/iai_core/telemetry"
	"golang.org/x/sync/errgroup"
	pb "geti.com/predict"

	"inference_gateway/app/entities"
	"inference_gateway/app/service"
)

const MaxConcurrentInferenceRequests = 100

var (
	labelIDsByModel = sync.Map{}
	labelIDsRegex   = regexp.MustCompile(`<label_ids\s+value="([^"]*)"`)
)

type Infer interface {
	One(ctx context.Context, request *entities.PredictionRequestData, includeXAI bool) (string, error)
	Batch(ctx context.Context, request *entities.BatchPredictionRequestData, includeXAI bool) ([][]byte, error)
}

type InferImpl struct {
	modelAccess    service.ModelAccessService
	videoRepo      storage.VideoRepository
	frameExtractor frames.CLIFrameExtractor
	semaCh         chan struct{}
}

func NewInferImpl(
	modelAccess service.ModelAccessService,
	videoRepo storage.VideoRepository,
	frameExtractor frames.CLIFrameExtractor,
) *InferImpl {
	return &InferImpl{
		modelAccess:    modelAccess,
		videoRepo:      videoRepo,
		frameExtractor: frameExtractor,
		semaCh:         make(chan struct{}, MaxConcurrentInferenceRequests),
	}
}

func (uc *InferImpl) One(
	ctx context.Context,
	request *entities.PredictionRequestData,
	includeXAI bool,
) (string, error) {
	replacer := strings.NewReplacer("\n", "", "\r", "")
	modelName := replacer.Replace(request.ProjectID.String()) + "-" + replacer.Replace(request.ModelID.String())

	inferParams := service.NewInferParameters(
		request.Media,
		modelName,
		includeXAI,
		request.Roi,
		request.LabelOnly,
		request.HyperParameters,
	)
	response, err := uc.modelAccess.InferImageBytes(ctx, *inferParams)
	if errors.Is(err, service.ErrModelNotFound) {
		logger.TracingLog(ctx).Infof("`Model not found` error encountered, attempting to recover model `%s`", modelName)
		response, err = uc.modelAccess.TryRecoverModel(ctx, *inferParams)
		if err != nil {
			return "", err
		}
	} else if err != nil {
		return "", err
	}

	return extractPredictionsPayload(modelName, response)
}

func extractPredictionsPayload(modelName string, response *pb.ModelInferResponse) (string, error) {
	if predictionParam, hasPredictions := response.GetParameters()["predictions"]; hasPredictions && predictionParam != nil {
		if prediction := predictionParam.GetStringParam(); prediction != "" {
			return prediction, nil
		}
	}

	bboxesOutput, bboxesRaw, hasBboxes := getOutputRawByName(response, "bboxes")
	_, labelsRaw, hasLabels := getOutputRawByName(response, "labels")
	if !hasBboxes || !hasLabels {
		return "", errors.New("prediction response missing 'predictions' parameter")
	}

	bboxes, err := decodeFloat32Tensor(bboxesRaw)
	if err != nil {
		return "", fmt.Errorf("failed to decode bboxes tensor: %w", err)
	}
	labels, err := decodeInt64Tensor(labelsRaw)
	if err != nil {
		return "", fmt.Errorf("failed to decode labels tensor: %w", err)
	}

	bboxesShape := bboxesOutput.GetShape()
	if len(bboxesShape) < 2 {
		return "", fmt.Errorf("unexpected bboxes tensor shape: %v", bboxesShape)
	}

	numDetections := int(bboxesShape[len(bboxesShape)-2])
	attributesPerDetection := int(bboxesShape[len(bboxesShape)-1])
	if attributesPerDetection < 5 {
		return "", fmt.Errorf("unexpected bboxes tensor width: %d", attributesPerDetection)
	}

	maxDetections := min(numDetections, len(labels), len(bboxes)/attributesPerDetection)
	predictions := make([]map[string]any, 0, maxDetections)

	for i := range maxDetections {
		offset := i * attributesPerDetection
		x1 := bboxes[offset]
		y1 := bboxes[offset+1]
		x2 := bboxes[offset+2]
		y2 := bboxes[offset+3]
		score := bboxes[offset+4]

		if score <= 0 || math.IsNaN(float64(score)) {
			continue
		}

		if x2 < x1 {
			x1, x2 = x2, x1
		}
		if y2 < y1 {
			y1, y2 = y2, y1
		}

		width := x2 - x1
		height := y2 - y1
		if width <= 0 || height <= 0 {
			continue
		}

		predictions = append(predictions, map[string]any{
			"shape": map[string]any{
				"type":   "RECTANGLE",
				"x":      int(math.Round(float64(x1))),
				"y":      int(math.Round(float64(y1))),
				"width":  int(math.Round(float64(width))),
				"height": int(math.Round(float64(height))),
			},
			"labels": []map[string]any{{
				"id":          labelIDForIndex(modelName, labels[i]),
				"probability": min(max(float64(score), 0), 1),
			}},
		})
	}

	predictionsPayload, err := json.Marshal(map[string]any{"predictions": predictions})
	if err != nil {
		return "", fmt.Errorf("failed to serialize prediction payload: %w", err)
	}
	return string(predictionsPayload), nil
}

func labelIDForIndex(modelName string, index int64) string {
	labelIDs, err := getModelLabelIDs(modelName)
	if err != nil || index < 0 || int(index) >= len(labelIDs) {
		return strconv.FormatInt(index, 10)
	}
	return labelIDs[index]
}

func getModelLabelIDs(modelName string) ([]string, error) {
	if cached, ok := labelIDsByModel.Load(modelName); ok {
		return cached.([]string), nil
	}

	modelsDir := os.Getenv("OVMS_MODELS_DIR")
	if modelsDir == "" {
		modelsDir = "/ovms_models"
	}

	modelXMLPath := filepath.Join(modelsDir, modelName, "1", "model.xml")
	modelXMLContent, err := os.ReadFile(modelXMLPath)
	if err != nil {
		return nil, err
	}

	labelIDsMatch := labelIDsRegex.FindSubmatch(modelXMLContent)
	if len(labelIDsMatch) < 2 {
		return nil, fmt.Errorf("label_ids not found in %s", modelXMLPath)
	}

	labelIDs := strings.Fields(string(labelIDsMatch[1]))
	if len(labelIDs) == 0 {
		return nil, fmt.Errorf("label_ids are empty in %s", modelXMLPath)
	}

	labelIDsByModel.Store(modelName, labelIDs)
	return labelIDs, nil
}

func getOutputRawByName(
	response *pb.ModelInferResponse,
	name string,
) (*pb.ModelInferResponse_InferOutputTensor, []byte, bool) {
	outputs := response.GetOutputs()
	rawOutputs := response.GetRawOutputContents()
	for idx, output := range outputs {
		if output.GetName() == name && idx < len(rawOutputs) {
			return output, rawOutputs[idx], true
		}
	}
	return nil, nil, false
}

func decodeFloat32Tensor(raw []byte) ([]float32, error) {
	if len(raw)%4 != 0 {
		return nil, fmt.Errorf("byte length %d is not multiple of 4", len(raw))
	}
	out := make([]float32, len(raw)/4)
	for i := range out {
		bits := binary.LittleEndian.Uint32(raw[i*4 : (i+1)*4])
		out[i] = math.Float32frombits(bits)
	}
	return out, nil
}

func decodeInt64Tensor(raw []byte) ([]int64, error) {
	if len(raw)%8 != 0 {
		return nil, fmt.Errorf("byte length %d is not multiple of 8", len(raw))
	}
	out := make([]int64, len(raw)/8)
	for i := range out {
		out[i] = int64(binary.LittleEndian.Uint64(raw[i*8 : (i+1)*8]))
	}
	return out, nil
}

func (uc *InferImpl) Batch(
	ctx context.Context,
	request *entities.BatchPredictionRequestData,
	includeXAI bool,
) ([][]byte, error) {
	fullVideoID := sdkentities.NewFullVideoID(request.OrganizationID.String(),
		request.WorkspaceID.String(), request.ProjectID.String(),
		request.MediaInfo.DatasetID.String(), request.MediaInfo.VideoID.String())
	video, err := uc.videoRepo.LoadVideoByID(ctx, fullVideoID)
	if err != nil {
		return nil, err
	}

	c, span := telemetry.Tracer().Start(ctx, "inference-loop")
	defer span.End()
	totalRequests := (request.EndFrame-request.StartFrame)/request.FrameSkip + 1
	inferResults := make([][]byte, totalRequests)
	pr, pw := io.Pipe()
	doneCh := uc.frameExtractor.Start(c, video, request.StartFrame, request.EndFrame, request.FrameSkip, pw)
	g, gCtx := errgroup.WithContext(c)

	for frame := range uc.frameExtractor.Read(c, pr) {
		g.Go(func() error {
			select {
			case uc.semaCh <- struct{}{}:
				defer func() { <-uc.semaCh }()
			case <-gCtx.Done():
				return gCtx.Err()
			}

			req := request.ToSingleRequest()
			req.MediaInfo.FrameIndex = request.StartFrame + frame.Index*request.FrameSkip
			req.Media = bytes.NewBuffer(frame.Data)
			result, inferErr := uc.One(gCtx, req, includeXAI)
			if inferErr != nil {
				return inferErr
			}

			var (
				jsonData []byte
				reqErr   error
			)
			if includeXAI {
				jsonData, reqErr = req.ToExplainBytes(result)
			} else {
				jsonData, reqErr = req.ToPredictBytes(result)
			}
			if reqErr != nil {
				return fmt.Errorf("failed to construct JSON response from prediction string: %w", reqErr)
			}
			inferResults[frame.Index] = jsonData
			return nil
		})
	}

	err = <-doneCh
	if err != nil {
		telemetry.RecordError(span, err)
		return nil, fmt.Errorf("error during frame extraction process: %w", err)
	}
	if err = g.Wait(); err != nil {
		telemetry.RecordError(span, err)
		return nil, fmt.Errorf("error during one of the inference requests: %w", err)
	}

	return inferResults, nil
}
