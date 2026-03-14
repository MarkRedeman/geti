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
	request, reqErr := createModelInferRequest(ctx, params)
	if reqErr != nil {
		return nil, reqErr
	}
	response, err := s.ovmsClient.ModelInfer(ctx, request)
	if err != nil {
		logger.TracingLog(ctx).Infof("ovms grpc error encountered: %v", err)
		return nil, fmt.Errorf("failed to infer from OVMS: %w", err)
	}
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
