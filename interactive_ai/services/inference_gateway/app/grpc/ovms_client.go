// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package grpc

import (
	"fmt"

	"geti.com/iai_core/logger"
	"github.com/caarlos0/env/v11"
	pb "geti.com/predict"
	"google.golang.org/grpc"
)

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

func (oc *OVMSClient) GetModelReady(_ string) bool {
	// Compose bridge behavior: use infer-time readiness and avoid blocking status path.
	return true
}
