// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package grpc

import (
	"context"
	"fmt"
	"strings"
	"time"

	"geti.com/iai_core/logger"
	"github.com/caarlos0/env/v11"
	pb "geti.com/predict"
	"google.golang.org/grpc"
)

const OVMSModelReadyTimeoutSeconds = 3
const OVMSDefaultInputName = "image"

type ovmsConfig struct {
	Service string `env:"OVMS_SERVICE"        envDefault:"ovms"`
	Port    int    `env:"OVMS_PORT"           envDefault:"9000"`
	Address string `env:"OVMS_ADDRESS,expand" envDefault:"passthrough:///$OVMS_SERVICE:${OVMS_PORT}"`
}

type OVMSClient struct {
	pb.GRPCInferenceServiceClient

	conn *grpc.ClientConn
}

func NewOVMSClient() (*OVMSClient, error) {
	cfg := ovmsConfig{}
	err := env.Parse(&cfg)
	if err != nil {
		return nil, fmt.Errorf("failed to parse env vars: %w", err)
	}

	logger.Log().Infof("Creating a new gRPC 'channel' for OVMS target URI: %s...", cfg.Address)
	conn, err := NewGRPCClient(cfg.Address)
	if err != nil {
		return nil, fmt.Errorf("cannot create a new grpc client for %s: %w", cfg.Address, err)
	}
	logger.Log().Info("OVMS gRPC client successfully created.")
	return &OVMSClient{
		GRPCInferenceServiceClient: pb.NewGRPCInferenceServiceClient(conn),
		conn:                       conn,
	}, nil
}

func (oc *OVMSClient) Close() error {
	logger.Log().Info("Closing OVMS connection.")
	if err := oc.conn.Close(); err != nil {
		return fmt.Errorf("error upon closing OVMS gRPC connection: %w", err)
	}
	return nil
}

func (oc *OVMSClient) GetModelReady(ctx context.Context, modelID string) bool {
	req := &pb.ModelReadyRequest{Name: modelID}
	rCtx, cancel := context.WithTimeout(ctx, time.Duration(OVMSModelReadyTimeoutSeconds)*time.Second)
	defer cancel()
	resp, err := oc.ModelReady(rCtx, req)
	if err != nil {
		logger.TracingLog(ctx).Infof("OVMS model readiness check failed for `%s`: %v", modelID, err)
		return false
	}
	return resp.GetReady()
}

func (oc *OVMSClient) GetInputName(ctx context.Context, modelID string) string {
	rCtx, cancel := context.WithTimeout(ctx, time.Duration(OVMSModelReadyTimeoutSeconds)*time.Second)
	defer cancel()

	resp, err := oc.ModelMetadata(rCtx, &pb.ModelMetadataRequest{Name: modelID})
	if err != nil || len(resp.GetInputs()) == 0 {
		logger.TracingLog(ctx).Infof(
			"OVMS metadata unavailable for `%s` (err=%v), using default input `%s`",
			modelID,
			err,
			OVMSDefaultInputName,
		)
		return OVMSDefaultInputName
	}

	return resp.GetInputs()[0].GetName()
}

func (oc *OVMSClient) IsMediapipeGraph(ctx context.Context, modelID string) bool {
	rCtx, cancel := context.WithTimeout(ctx, time.Duration(OVMSModelReadyTimeoutSeconds)*time.Second)
	defer cancel()

	resp, err := oc.ModelMetadata(rCtx, &pb.ModelMetadataRequest{Name: modelID})
	if err != nil {
		return false
	}

	platform := strings.ToLower(resp.GetPlatform())
	return strings.Contains(platform, "mediapipe")
}
