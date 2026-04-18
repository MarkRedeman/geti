// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package service

import (
	"bytes"
	"context"
	"errors"
	"image/jpeg"
	"testing"

	pb "geti.com/predict"
	predictmock "geti.com/predict/mock"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"

	"inference_gateway/app/entities"
	"inference_gateway/app/grpc"
	testhelpers "inference_gateway/app/test_helpers"
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

	img := testhelpers.GetUniformTestImage(16, 12, uint8(155))
	buf := new(bytes.Buffer)
	err := jpeg.Encode(buf, img, nil)
	require.NoError(t, err)
	params := NewInferParameters(buf, "project-model", false, entities.Roi{}, false, nil)

	inferenceMock.EXPECT().ModelReady(mock.Anything, &pb.ModelReadyRequest{Name: "project-model"}).
		Return(&pb.ModelReadyResponse{Ready: true}, nil).Once()
	inferenceMock.EXPECT().ModelMetadata(mock.Anything, &pb.ModelMetadataRequest{Name: "project-model"}).
		Return(&pb.ModelMetadataResponse{Inputs: []*pb.ModelMetadataResponse_TensorMetadata{{Name: "image"}}}, nil).Once()
	inferenceMock.EXPECT().ModelMetadata(mock.Anything, &pb.ModelMetadataRequest{Name: "project-model"}).
		Return(&pb.ModelMetadataResponse{Platform: "OpenVINO Model Server"}, nil).Once()
	inferenceMock.EXPECT().ModelInfer(mock.Anything, mock.MatchedBy(func(req *pb.ModelInferRequest) bool {
		if req == nil || len(req.Inputs) == 0 {
			return false
		}
		return req.Inputs[0].GetName() == "image" &&
			req.Inputs[0].GetDatatype() == "UINT8" &&
			len(req.Inputs[0].GetShape()) == 4 &&
			req.Inputs[0].GetShape()[0] == 1 &&
			req.Inputs[0].GetShape()[1] == 12 &&
			req.Inputs[0].GetShape()[2] == 16 &&
			req.Inputs[0].GetShape()[3] == 3
	})).
		Return(&pb.ModelInferResponse{}, nil).Once()

	resp, err := service.TryRecoverModel(context.Background(), *params)
	require.NoError(t, err)
	assert.NotNil(t, resp)
}

func TestOVMSModelAccessService_InferImageBytes_MediapipeBytesInput(t *testing.T) {
	inferenceMock := predictmock.NewMockGRPCInferenceServiceClient(t)
	client := &grpc.OVMSClient{GRPCInferenceServiceClient: inferenceMock}
	service := NewOVMSModelAccessService(client)

	buf := bytes.NewBuffer([]byte("jpeg-bytes"))
	params := NewInferParameters(buf, "project-model", false, entities.Roi{}, false, nil)

	inferenceMock.EXPECT().ModelMetadata(mock.Anything, &pb.ModelMetadataRequest{Name: "project-model"}).
		Return(&pb.ModelMetadataResponse{Inputs: []*pb.ModelMetadataResponse_TensorMetadata{{Name: "image"}}}, nil).Once()
	inferenceMock.EXPECT().ModelMetadata(mock.Anything, &pb.ModelMetadataRequest{Name: "project-model"}).
		Return(&pb.ModelMetadataResponse{Platform: "mediapipe"}, nil).Once()
	inferenceMock.EXPECT().ModelInfer(mock.Anything, mock.MatchedBy(func(req *pb.ModelInferRequest) bool {
		if req == nil || len(req.Inputs) == 0 {
			return false
		}
		input := req.Inputs[0]
		if input.GetDatatype() != "BYTES" || len(input.GetShape()) != 1 || input.GetShape()[0] != 1 {
			return false
		}
		contents := input.GetContents()
		return contents != nil && len(contents.GetBytesContents()) == 1 && string(contents.GetBytesContents()[0]) == "jpeg-bytes"
	})).Return(&pb.ModelInferResponse{}, nil).Once()

	resp, err := service.InferImageBytes(context.Background(), *params)
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
