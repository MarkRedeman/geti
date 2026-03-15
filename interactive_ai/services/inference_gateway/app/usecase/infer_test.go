// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package usecase

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sync"
	"testing"

	sdkentities "geti.com/iai_core/entities"
	"geti.com/iai_core/frames"
	"geti.com/iai_core/storage"
	pb "geti.com/predict"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"

	"inference_gateway/app/entities"
	"inference_gateway/app/service"
)

func MockDoneCh() <-chan error {
	done := make(chan error)
	go func() {
		done <- nil
		close(done)
	}()
	return done
}

func MockFrameCh(total int) <-chan *frames.FrameData {
	frameCh := make(chan *frames.FrameData)
	go func() {
		for i := range total {
			frameCh <- &frames.FrameData{
				Index: i,
				Data:  []byte("test"),
			}
		}
		close(frameCh)
	}()
	return frameCh
}

func TestInferBatch(t *testing.T) {
	ctx := t.Context()
	fullVideoID := sdkentities.GetFullVideoID(t)
	start, end, skip := 0, 199, 10
	total := (end-start)/skip + 1
	video := &sdkentities.Video{FilePath: "video_path", FPS: 25}
	// Prepare test variables
	mediaInfo := entities.MediaInfo{
		VideoID:   fullVideoID.VideoID,
		DatasetID: fullVideoID.DatasetID,
	}
	hyperParams := "{'confidence_treshold':0.35}"
	batchRequest := entities.BatchPredictionRequestData{
		OrganizationID:  fullVideoID.OrganizationID,
		WorkspaceID:     fullVideoID.WorkspaceID,
		ProjectID:       fullVideoID.ProjectID,
		ModelID:         sdkentities.ID{ID: "000000000000000000000003"},
		MediaInfo:       &mediaInfo,
		StartFrame:      start,
		EndFrame:        end,
		FrameSkip:       skip,
		HyperParameters: &hyperParams,
	}

	mockModelAccess := service.NewMockModelAccessService(t)
	mockVideoRepo := storage.NewMockVideoRepository(t)
	mockFrameExtractor := frames.NewMockCLIFrameExtractor(t)

	tests := []struct {
		name            string
		setupMocks      func()
		actionAndAssert func(t *testing.T)
	}{
		{
			name: "Explain",
			setupMocks: func() {
				mockVideoRepo.EXPECT().
					LoadVideoByID(ctx, fullVideoID).
					Return(video, nil).
					Once()

				mockFrameExtractor.EXPECT().
					Start(mock.AnythingOfType("*context.valueCtx"), video, start, end, skip, mock.AnythingOfType("*io.PipeWriter")).
					Return(MockDoneCh())
				mockFrameExtractor.EXPECT().
					Read(mock.AnythingOfType("*context.valueCtx"), mock.AnythingOfType("*io.PipeReader")).
					Return(MockFrameCh(total))

				respParams := map[string]*pb.InferParameter{"predictions": {
					ParameterChoice: &pb.InferParameter_StringParam{StringParam: `{"score": 0.7}`}}}
				inferResp := &pb.ModelInferResponse{Parameters: respParams}
				mockModelAccess.EXPECT().
					InferImageBytes(mock.AnythingOfType("*context.cancelCtx"), mock.AnythingOfType("InferParameters")).
					Return(inferResp, nil).
					Times(total)
			},
			actionAndAssert: func(t *testing.T) {
				infer := NewInferImpl(mockModelAccess, mockVideoRepo, mockFrameExtractor)
				result, err := infer.Batch(ctx, &batchRequest, true)
				require.NoError(t, err)
				assert.NotNil(t, result)
				assert.Len(t, result, total)
				for i, item := range result {
					assert.NotNil(t, item)
					assert.Contains(t, string(item), "maps")
					assert.Contains(t, string(item), fmt.Sprintf("\"frame_index\":%d", i*skip))
				}
			},
		},
		{
			name: "Predict",
			setupMocks: func() {
				mockVideoRepo.EXPECT().
					LoadVideoByID(ctx, fullVideoID).
					Return(video, nil).
					Once()

				mockFrameExtractor.EXPECT().
					Start(mock.AnythingOfType("*context.valueCtx"), video, start, end, skip, mock.AnythingOfType("*io.PipeWriter")).
					Return(MockDoneCh())
				mockFrameExtractor.EXPECT().
					Read(mock.AnythingOfType("*context.valueCtx"), mock.AnythingOfType("*io.PipeReader")).
					Return(MockFrameCh(total))

				respParams := map[string]*pb.InferParameter{"predictions": {
					ParameterChoice: &pb.InferParameter_StringParam{StringParam: `{"score": 0.7}`}}}
				inferResp := &pb.ModelInferResponse{Parameters: respParams}
				mockModelAccess.EXPECT().
					InferImageBytes(mock.AnythingOfType("*context.cancelCtx"), mock.AnythingOfType("InferParameters")).
					Return(inferResp, nil).
					Times(total)
			},
			actionAndAssert: func(t *testing.T) {
				infer := NewInferImpl(mockModelAccess, mockVideoRepo, mockFrameExtractor)
				result, err := infer.Batch(ctx, &batchRequest, false)
				require.NoError(t, err)
				assert.NotNil(t, result)
				assert.Len(t, result, total)
				for i, item := range result {
					assert.NotNil(t, item)
					assert.Contains(t, string(item), "predictions")
					assert.Contains(t, string(item), fmt.Sprintf("\"frame_index\":%d", start+i*skip))
				}
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tt.setupMocks()
			tt.actionAndAssert(t)

			mockVideoRepo.ExpectedCalls = nil
			mockModelAccess.ExpectedCalls = nil
			mockFrameExtractor.ExpectedCalls = nil
		})
	}
}

func TestInferOne_MissingPredictionsParam(t *testing.T) {
	ctx := t.Context()
	mockModelAccess := service.NewMockModelAccessService(t)
	mockVideoRepo := storage.NewMockVideoRepository(t)
	mockFrameExtractor := frames.NewMockCLIFrameExtractor(t)

	request := &entities.PredictionRequestData{
		ProjectID: sdkentities.ID{ID: "69b6afc6c369ebbc276fd8ae"},
		ModelID:   sdkentities.ID{ID: "active"},
		Media:     bytes.NewBuffer([]byte("test-image")),
	}

	mockModelAccess.EXPECT().
		InferImageBytes(mock.Anything, mock.AnythingOfType("service.InferParameters")).
		Return(&pb.ModelInferResponse{Parameters: map[string]*pb.InferParameter{}}, nil).
		Once()

	infer := NewInferImpl(mockModelAccess, mockVideoRepo, mockFrameExtractor)
	_, err := infer.One(ctx, request, false)
	require.Error(t, err)
	assert.ErrorContains(t, err, "missing 'predictions' parameter")
}

func TestInferOne_BuildsPredictionsFromOVMSTensors(t *testing.T) {
	ctx := t.Context()
	labelIDsByModel = sync.Map{}
	modelsDir := t.TempDir()
	t.Setenv("OVMS_MODELS_DIR", modelsDir)
	modelName := "69b6afc6c369ebbc276fd8ae-active"
	modelDir := filepath.Join(modelsDir, modelName, "1")
	require.NoError(t, os.MkdirAll(modelDir, 0o755))
	modelXML := `<net><rt_info><model_info><label_ids value="111111111111111111111111 222222222222222222222222 333333333333333333333333 444444444444444444444444 555555555555555555555555 666666666666666666666666 777777777777777777777777 888888888888888888888888" /></model_info></rt_info></net>`
	require.NoError(t, os.WriteFile(filepath.Join(modelDir, "model.xml"), []byte(modelXML), 0o644))

	mockModelAccess := service.NewMockModelAccessService(t)
	mockVideoRepo := storage.NewMockVideoRepository(t)
	mockFrameExtractor := frames.NewMockCLIFrameExtractor(t)

	request := &entities.PredictionRequestData{
		ProjectID: sdkentities.ID{ID: "69b6afc6c369ebbc276fd8ae"},
		ModelID:   sdkentities.ID{ID: "active"},
		Media:     bytes.NewBuffer([]byte("test-image")),
	}

	bboxes := []float32{10, 20, 30, 45, 0.9}
	bboxesRaw := make([]byte, 4*len(bboxes))
	for i, value := range bboxes {
		binary.LittleEndian.PutUint32(bboxesRaw[i*4:(i+1)*4], math.Float32bits(value))
	}
	labelsRaw := make([]byte, 8)
	binary.LittleEndian.PutUint64(labelsRaw, uint64(7))

	resp := &pb.ModelInferResponse{
		Outputs: []*pb.ModelInferResponse_InferOutputTensor{
			{Name: "bboxes", Datatype: "FP32", Shape: []int64{1, 1, 5}},
			{Name: "labels", Datatype: "INT64", Shape: []int64{1, 1}},
		},
		RawOutputContents: [][]byte{bboxesRaw, labelsRaw},
	}

	mockModelAccess.EXPECT().
		InferImageBytes(mock.Anything, mock.Anything).
		Return(resp, nil).
		Once()

	infer := NewInferImpl(mockModelAccess, mockVideoRepo, mockFrameExtractor)
	predictionStr, err := infer.One(ctx, request, false)
	require.NoError(t, err)

	var payload map[string][]map[string]any
	require.NoError(t, json.Unmarshal([]byte(predictionStr), &payload))
	assert.Contains(t, payload, "predictions")
	if assert.Len(t, payload["predictions"], 1) {
		prediction := payload["predictions"][0]
		shape := prediction["shape"].(map[string]any)
		labels := prediction["labels"].([]any)
		label := labels[0].(map[string]any)
		assert.Equal(t, "RECTANGLE", shape["type"])
		assert.EqualValues(t, 10, shape["x"])
		assert.EqualValues(t, 20, shape["y"])
		assert.EqualValues(t, 20, shape["width"])
		assert.EqualValues(t, 25, shape["height"])
		assert.Equal(t, "888888888888888888888888", label["id"])
	}
}
