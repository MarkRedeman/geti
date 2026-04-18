// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package service

import (
	"context"
	"fmt"
	"time"

	"geti.com/iai_core/logger"
	pb "geti.com/predict"

	"inference_gateway/app/grpc"
)

type OVMSModelAccessService struct {
	ovmsClient *grpc.OVMSClient
}

func NewOVMSModelAccessService(ovmsClient *grpc.OVMSClient) *OVMSModelAccessService {
	return &OVMSModelAccessService{ovmsClient: ovmsClient}
}

func (s *OVMSModelAccessService) InferImageBytes(
	ctx context.Context,
	params InferParameters,
) (*pb.ModelInferResponse, error) {
	inputName := s.ovmsClient.GetInputName(ctx, params.pipelineName)
	isMediapipe := s.ovmsClient.IsMediapipeGraph(ctx, params.pipelineName)

	var (
		request *pb.ModelInferRequest
		reqErr  error
	)
	if isMediapipe {
		request, reqErr = createMediapipeModelInferRequest(ctx, params, inputName)
	} else {
		request, reqErr = createModelInferRequestWithInputName(ctx, params, inputName)
	}
	if reqErr != nil {
		return nil, reqErr
	}
	response, err := s.ovmsClient.ModelInfer(ctx, request)
	if err != nil {
		logger.TracingLog(ctx).Infof("ovms grpc error encountered: %v", err)
		return nil, fmt.Errorf("failed to infer from OVMS: %w", err)
	}
	logger.TracingLog(ctx).Infof(
		"OVMS infer response summary: parameters=%d outputs=%d raw_output_contents=%d",
		len(response.GetParameters()),
		len(response.GetOutputs()),
		len(response.GetRawOutputContents()),
	)
	return response, nil
}

func (s *OVMSModelAccessService) TryRecoverModel(
	ctx context.Context,
	params InferParameters,
) (*pb.ModelInferResponse, error) {
	for range ModelReadyRetries {
		if s.ovmsClient.GetModelReady(ctx, params.pipelineName) {
			return s.InferImageBytes(ctx, params)
		}
		time.Sleep(time.Duration(ModelRecoveryStatusCheckIntervalMilliSeconds) * time.Millisecond)
	}
	return nil, ErrModelNotFound
}

func (s *OVMSModelAccessService) IsModelReady(ctx context.Context, modelID string) bool {
	return s.ovmsClient.GetModelReady(ctx, modelID)
}
