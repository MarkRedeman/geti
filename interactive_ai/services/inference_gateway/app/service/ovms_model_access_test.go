// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package service

import (
	"bytes"
	"context"
	"errors"
	"testing"

	pb "geti.com/predict"
	predictmock "geti.com/predict/mock"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"

	"inference_gateway/app/entities"
	"inference_gateway/app/grpc"
)

func TestOVMSModelAccessService_IsModelReady(t *testing.T) {
	inferenceMock := predictmock.NewMockGRPCInferenceServiceClient(t)
	client := &grpc.OVMSClient{GRPCInferenceServiceClient: inferenceMock}
	service := NewOVMSModelAccessService(client)

	inferenceMock.EXPECT().ModelReady(mock.Anything, &pb.ModelReadyRequest{Name: "p1"}).
		Return(&pb.ModelReadyResponse{Ready: true}, nil).Once()

	ready := service.IsModelReady(context.Background(), "p1")
	assert.True(t, ready)
}

func TestOVMSModelAccessService_TryRecoverModel_WhenReady(t *testing.T) {
	inferenceMock := predictmock.NewMockGRPCInferenceServiceClient(t)
	client := &grpc.OVMSClient{GRPCInferenceServiceClient: inferenceMock}
	service := NewOVMSModelAccessService(client)

	buf := bytes.NewBuffer([]byte("image-bytes"))
	params := NewInferParameters(buf, "project-model", false, entities.Roi{}, false, nil)

	inferenceMock.EXPECT().ModelReady(mock.Anything, &pb.ModelReadyRequest{Name: "project-model"}).
		Return(&pb.ModelReadyResponse{Ready: true}, nil).Once()
	inferenceMock.EXPECT().ModelInfer(mock.Anything, mock.AnythingOfType("*predictv2.ModelInferRequest")).
		Return(&pb.ModelInferResponse{}, nil).Once()

	resp, err := service.TryRecoverModel(context.Background(), *params)
	require.NoError(t, err)
	assert.NotNil(t, resp)
}

func TestOVMSModelAccessService_TryRecoverModel_NotReady(t *testing.T) {
	inferenceMock := predictmock.NewMockGRPCInferenceServiceClient(t)
	client := &grpc.OVMSClient{GRPCInferenceServiceClient: inferenceMock}
	service := NewOVMSModelAccessService(client)

	buf := bytes.NewBuffer([]byte("image-bytes"))
	params := NewInferParameters(buf, "project-model", false, entities.Roi{}, false, nil)

	inferenceMock.EXPECT().ModelReady(mock.Anything, &pb.ModelReadyRequest{Name: "project-model"}).
		Return(&pb.ModelReadyResponse{Ready: false}, nil).Times(ModelReadyRetries)

	resp, err := service.TryRecoverModel(context.Background(), *params)
	assert.Nil(t, resp)
	assert.True(t, errors.Is(err, ErrModelNotFound))
}
