// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package roles

import (
	"fmt"

	v1 "github.com/authzed/authzed-go/proto/authzed/api/v1"
	"gorm.io/gorm"
)

type IRolesManager interface {
	WriteRelationship(relation string, subject *v1.SubjectReference, resource *v1.ObjectReference, operation v1.RelationshipUpdate_Operation) error
	GetRelationships(filter *v1.RelationshipFilter) ([]*v1.Relationship, error)
	ChangeOrganizationRelation(resourceType string, resourceID string, relations []string, organizationID string, operation v1.RelationshipUpdate_Operation) error
	AddServiceAccountToUser(userID string, serviceAccountID string) error
	DeleteServiceAccountFromUser(userID string, serviceAccountID string) error
	GetUserRelationships(userID string, resourceType string) ([]*v1.Relationship, error)
	GetOrganizationRelationships(orgID string, relation string) ([]*v1.Relationship, error)
	GetRelationshipsByOrganization(organizationID string, resourceType string) ([]*v1.Relationship, error)
	GetWorkspaceParentOrganizationID(workspaceID string) (string, error)
	GetProjectParentWorkspaceID(projectID string) (string, error)
	GetUserAllRelationships(userID string) ([]*v1.Relationship, error)
	GetUserOrganization(organizationID string, userID string) ([]*v1.Relationship, error)
	GetUserOrgWorkspaces(organizationID string, userID string) ([]*v1.Relationship, error)
	GetUserOrgProjects(organizationID string, userID string, orgWorkspaceRelationships []*v1.Relationship) ([]*v1.Relationship, error)
	GetUserAllRelationshipsByOrganization(organizationID string, userID string) ([]*v1.Relationship, error)
	CheckRelationshipToDelete(relationship *v1.Relationship, orgID string) (bool, error)
	ChangeUserRelation(resourceType string, resourceID string, relations []string, userID string, operation v1.RelationshipUpdate_Operation) error
	GetAdminSubjectUsers() ([]string, error)
}

var rolesDB *gorm.DB

func SetDB(db *gorm.DB) {
	rolesDB = db
}

func NewRolesManager() (IRolesManager, error) {
	if rolesDB == nil {
		return nil, fmt.Errorf("roles database is not initialized")
	}
	return NewDBRolesManager(rolesDB), nil
}
