// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package models

import (
	"database/sql"
	"time"

	"github.com/google/uuid"
)

type UserCredential struct {
	ID           uuid.UUID     `gorm:"primaryKey;type:uuid;default:gen_random_uuid()"`
	UserID       uuid.UUID     `gorm:"type:uuid;not null;uniqueIndex"`
	PasswordHash string        `gorm:"size:512;not null"`
	EmailToken   string        `gorm:"size:512;default:null"`
	Registered   bool          `gorm:"not null;default:true"`
	CreatedAt    time.Time     `gorm:"autoCreateTime"`
	ModifiedAt   *sql.NullTime `gorm:"autoUpdateTime"`
}

func (UserCredential) TableName() string {
	return "user_credentials"
}
