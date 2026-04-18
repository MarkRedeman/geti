// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package grpc

import (
	"context"
	"testing"

	pb "geti.com/predict"
	predictmock "geti.com/predict/mock"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func TestOVMSClient_GetModelReady(t *testing.T) {
	inferenceMock := predictmock.NewMockGRPCInferenceServiceClient(t)
	client := &OVMSClient{GRPCInferenceServiceClient: inferenceMock}

	request := &pb.ModelReadyRequest{Name: "project-model"}
	response := &pb.ModelReadyResponse{Ready: true}
	inferenceMock.EXPECT().ModelReady(mock.Anything, request).Return(response, nil).Once()

	ready := client.GetModelReady(context.Background(), "project-model")
	assert.True(t, ready)
}

func TestOVMSClient_GetModelReady_Error(t *testing.T) {
	inferenceMock := predictmock.NewMockGRPCInferenceServiceClient(t)
	client := &OVMSClient{GRPCInferenceServiceClient: inferenceMock}

	request := &pb.ModelReadyRequest{Name: "project-model"}
	inferenceMock.EXPECT().ModelReady(mock.Anything, request).
		Return(nil, status.Error(codes.NotFound, "not found")).Once()

	ready := client.GetModelReady(context.Background(), "project-model")
	assert.False(t, ready)
}
