// Copyright (C) 2026 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package models

import "time"

type AuthorizationRelationship struct {
	ID           uint      `gorm:"primaryKey"`
	ResourceType string    `gorm:"size:64;not null;index:idx_auth_res,priority:1"`
	ResourceID   string    `gorm:"size:128;not null;index:idx_auth_res,priority:2"`
	Relation     string    `gorm:"size:128;not null;index:idx_auth_rel,priority:1"`
	SubjectType  string    `gorm:"size:64;not null;index:idx_auth_subj,priority:1"`
	SubjectID    string    `gorm:"size:128;not null;index:idx_auth_subj,priority:2"`
	SubjectRel   string    `gorm:"size:128"`
	CreatedAt    time.Time `gorm:"autoCreateTime"`
	UpdatedAt    time.Time `gorm:"autoUpdateTime"`
}

func (AuthorizationRelationship) TableName() string {
	return "authorization_relationships"
}
