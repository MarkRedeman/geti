// Copyright (C) 2026 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package roles

import (
	"encoding/base64"
	"errors"
	"fmt"

	"account_service/app/common/utils"
	"account_service/app/models"

	v1 "github.com/authzed/authzed-go/proto/authzed/api/v1"
	"gorm.io/gorm"
)

type DBRolesManager struct {
	db *gorm.DB
}

var supportedUserResourceTypes = [...]string{"workspace", "project", "organization"}

var logger = utils.InitializeLogger()

var supportedResourceTypes = map[string]bool{
	"organization":    true,
	"workspace":       true,
	"project":         true,
	"job":             true,
	"user":            true,
	"user_directory":  true,
	"service_account": true,
}

func NewDBRolesManager(db *gorm.DB) *DBRolesManager {
	return &DBRolesManager{db: db}
}

func (m *DBRolesManager) WriteRelationship(relation string, subject *v1.SubjectReference, resource *v1.ObjectReference, operation v1.RelationshipUpdate_Operation) error {
	if relation == "" || subject == nil || subject.Object == nil || resource == nil {
		return NewInvalidRoleError("invalid relationship payload")
	}
	if !supportedResourceTypes[resource.ObjectType] {
		return NewInvalidRoleError(fmt.Sprintf("unsupported resource type: %s", resource.ObjectType))
	}

	record := models.AuthorizationRelationship{
		ResourceType: resource.ObjectType,
		ResourceID:   resource.ObjectId,
		Relation:     relation,
		SubjectType:  subject.Object.ObjectType,
		SubjectID:    subject.Object.ObjectId,
	}
	if subject.OptionalRelation != "" {
		record.SubjectRel = subject.OptionalRelation
	}

	switch operation {
	case v1.RelationshipUpdate_OPERATION_CREATE:
		var existing int64
		err := m.db.Model(&models.AuthorizationRelationship{}).
			Where("resource_type = ? AND resource_id = ? AND relation = ? AND subject_type = ? AND subject_id = ? AND COALESCE(subject_rel, '') = ?",
				record.ResourceType,
				record.ResourceID,
				record.Relation,
				record.SubjectType,
				record.SubjectID,
				record.SubjectRel,
			).
			Count(&existing).Error
		if err != nil {
			return err
		}
		if existing > 0 {
			relationshipUpdate := v1.RelationshipUpdate{Operation: operation, Relationship: &v1.Relationship{Resource: resource, Relation: relation, Subject: subject}}
			return NewRoleAlreadyExistsError("relationship already exists", &relationshipUpdate)
		}
		return m.db.Create(&record).Error
	case v1.RelationshipUpdate_OPERATION_TOUCH:
		var existing models.AuthorizationRelationship
		err := m.db.Where("resource_type = ? AND resource_id = ? AND relation = ? AND subject_type = ? AND subject_id = ? AND COALESCE(subject_rel, '') = ?",
			record.ResourceType,
			record.ResourceID,
			record.Relation,
			record.SubjectType,
			record.SubjectID,
			record.SubjectRel,
		).First(&existing).Error
		if err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return m.db.Create(&record).Error
			}
			return err
		}
		return nil
	case v1.RelationshipUpdate_OPERATION_DELETE:
		return m.db.Where("resource_type = ? AND resource_id = ? AND relation = ? AND subject_type = ? AND subject_id = ? AND COALESCE(subject_rel, '') = ?",
			record.ResourceType,
			record.ResourceID,
			record.Relation,
			record.SubjectType,
			record.SubjectID,
			record.SubjectRel,
		).Delete(&models.AuthorizationRelationship{}).Error
	default:
		return NewInvalidRoleError("unsupported relationship operation")
	}
}

func (m *DBRolesManager) GetRelationships(filter *v1.RelationshipFilter) ([]*v1.Relationship, error) {
	query := m.db.Model(&models.AuthorizationRelationship{})
	if filter != nil {
		if filter.ResourceType != "" {
			query = query.Where("resource_type = ?", filter.ResourceType)
		}
		if filter.OptionalResourceId != "" {
			query = query.Where("resource_id = ?", filter.OptionalResourceId)
		}
		if filter.OptionalRelation != "" {
			query = query.Where("relation = ?", filter.OptionalRelation)
		}
		if filter.OptionalSubjectFilter != nil {
			sf := filter.OptionalSubjectFilter
			if sf.SubjectType != "" {
				query = query.Where("subject_type = ?", sf.SubjectType)
			}
			if sf.OptionalSubjectId != "" {
				query = query.Where("subject_id = ?", sf.OptionalSubjectId)
			}
			if sf.OptionalRelation != nil && sf.OptionalRelation.Relation != "" {
				query = query.Where("subject_rel = ?", sf.OptionalRelation.Relation)
			}
		}
	}

	var rows []models.AuthorizationRelationship
	if err := query.Find(&rows).Error; err != nil {
		return nil, err
	}

	relationships := make([]*v1.Relationship, 0, len(rows))
	for _, row := range rows {
		subject := &v1.SubjectReference{Object: &v1.ObjectReference{ObjectType: row.SubjectType, ObjectId: row.SubjectID}}
		subject.OptionalRelation = row.SubjectRel
		relationships = append(relationships, &v1.Relationship{
			Resource: &v1.ObjectReference{ObjectType: row.ResourceType, ObjectId: row.ResourceID},
			Relation: row.Relation,
			Subject:  subject,
		})
	}
	return relationships, nil
}

func (m *DBRolesManager) ChangeUserRelation(resourceType string, resourceID string, relations []string, userID string, operation v1.RelationshipUpdate_Operation) error {
	if _, err := base64.StdEncoding.DecodeString(userID); err != nil {
		userID = base64.StdEncoding.EncodeToString([]byte(userID))
	}
	userSubject := v1.SubjectReference{Object: &v1.ObjectReference{ObjectType: "user", ObjectId: userID}}
	resource := v1.ObjectReference{ObjectType: resourceType, ObjectId: resourceID}
	for _, relation := range relations {
		if err := m.WriteRelationship(relation, &userSubject, &resource, operation); err != nil {
			return err
		}
	}
	return nil
}

func (m *DBRolesManager) ChangeOrganizationRelation(resourceType string, resourceID string, relations []string, organizationID string, operation v1.RelationshipUpdate_Operation) error {
	subject := v1.SubjectReference{Object: &v1.ObjectReference{ObjectType: "organization", ObjectId: organizationID}}
	resource := v1.ObjectReference{ObjectType: resourceType, ObjectId: resourceID}
	for _, relation := range relations {
		if err := m.WriteRelationship(relation, &subject, &resource, operation); err != nil {
			return err
		}
	}
	return nil
}

func (m *DBRolesManager) AddServiceAccountToUser(userID string, serviceAccountID string) error {
	if _, err := base64.StdEncoding.DecodeString(userID); err != nil {
		userID = base64.StdEncoding.EncodeToString([]byte(userID))
	}
	if _, err := base64.StdEncoding.DecodeString(serviceAccountID); err != nil {
		serviceAccountID = base64.StdEncoding.EncodeToString([]byte(serviceAccountID))
	}
	subject := &v1.SubjectReference{Object: &v1.ObjectReference{ObjectType: "service_account", ObjectId: serviceAccountID}}
	resource := &v1.ObjectReference{ObjectType: "user", ObjectId: userID}
	return m.WriteRelationship("service_accounts", subject, resource, v1.RelationshipUpdate_OPERATION_TOUCH)
}

func (m *DBRolesManager) DeleteServiceAccountFromUser(userID string, serviceAccountID string) error {
	if _, err := base64.StdEncoding.DecodeString(userID); err != nil {
		userID = base64.StdEncoding.EncodeToString([]byte(userID))
	}
	if _, err := base64.StdEncoding.DecodeString(serviceAccountID); err != nil {
		serviceAccountID = base64.StdEncoding.EncodeToString([]byte(serviceAccountID))
	}
	subject := &v1.SubjectReference{Object: &v1.ObjectReference{ObjectType: "service_account", ObjectId: serviceAccountID}}
	resource := &v1.ObjectReference{ObjectType: "user", ObjectId: userID}
	return m.WriteRelationship("service_accounts", subject, resource, v1.RelationshipUpdate_OPERATION_DELETE)
}

func (m *DBRolesManager) GetUserRelationships(userID string, resourceType string) ([]*v1.Relationship, error) {
	userID = base64.StdEncoding.EncodeToString([]byte(userID))
	filter := v1.RelationshipFilter{
		ResourceType:          resourceType,
		OptionalSubjectFilter: &v1.SubjectFilter{SubjectType: "user", OptionalSubjectId: userID},
	}
	relationships, err := m.GetRelationships(&filter)
	if err != nil {
		return nil, err
	}
	for idx, rel := range relationships {
		decoded, err := base64.StdEncoding.DecodeString(rel.Subject.Object.ObjectId)
		if err == nil {
			relationships[idx].Subject.Object.ObjectId = string(decoded)
		}
	}
	return relationships, nil
}

func (m *DBRolesManager) GetOrganizationRelationships(orgID string, relation string) ([]*v1.Relationship, error) {
	filter := v1.RelationshipFilter{ResourceType: "organization", OptionalRelation: relation, OptionalResourceId: orgID}
	relationships, err := m.GetRelationships(&filter)
	if err != nil {
		return nil, err
	}
	for idx, rel := range relationships {
		decoded, err := base64.StdEncoding.DecodeString(rel.Subject.Object.ObjectId)
		if err == nil {
			relationships[idx].Subject.Object.ObjectId = string(decoded)
		}
	}
	return relationships, nil
}

func (m *DBRolesManager) GetRelationshipsByOrganization(organizationID string, resourceType string) ([]*v1.Relationship, error) {
	filter := v1.RelationshipFilter{
		ResourceType:          resourceType,
		OptionalSubjectFilter: &v1.SubjectFilter{SubjectType: "organization", OptionalSubjectId: organizationID},
	}
	return m.GetRelationships(&filter)
}

func (m *DBRolesManager) GetWorkspaceParentOrganizationID(workspaceID string) (string, error) {
	filter := v1.RelationshipFilter{ResourceType: "workspace", OptionalResourceId: workspaceID, OptionalRelation: "parent_organization"}
	relationships, err := m.GetRelationships(&filter)
	if err != nil {
		return "", err
	}
	if len(relationships) < 1 {
		return "", errors.New("no parent organization found")
	}
	return relationships[0].Subject.Object.ObjectId, nil
}

func (m *DBRolesManager) GetProjectParentWorkspaceID(projectID string) (string, error) {
	filter := v1.RelationshipFilter{ResourceType: "project", OptionalResourceId: projectID, OptionalRelation: "parent_workspace"}
	relationships, err := m.GetRelationships(&filter)
	if err != nil {
		return "", err
	}
	if len(relationships) < 1 {
		return "", errors.New("no parent workspace")
	}
	return relationships[0].Subject.Object.ObjectId, nil
}

func (m *DBRolesManager) GetUserAllRelationships(userID string) ([]*v1.Relationship, error) {
	var all []*v1.Relationship
	for _, resourceType := range supportedUserResourceTypes {
		rels, err := m.GetUserRelationships(userID, resourceType)
		if err != nil {
			return all, err
		}
		all = append(all, rels...)
	}
	return all, nil
}

func (m *DBRolesManager) CheckRelationshipToDelete(relationship *v1.Relationship, orgID string) (bool, error) {
	switch relationship.Resource.ObjectType {
	case "organization":
		return relationship.Resource.ObjectId == orgID, nil
	case "workspace":
		workspaceOrgID, err := m.GetWorkspaceParentOrganizationID(relationship.Resource.ObjectId)
		if err != nil {
			return false, err
		}
		return workspaceOrgID == orgID, nil
	case "project":
		projectWorkspaceID, err := m.GetProjectParentWorkspaceID(relationship.Resource.ObjectId)
		if err != nil {
			return false, err
		}
		workspaceOrgID, err := m.GetWorkspaceParentOrganizationID(projectWorkspaceID)
		if err != nil {
			return false, err
		}
		return workspaceOrgID == orgID, nil
	default:
		return false, nil
	}
}

func (m *DBRolesManager) GetUserOrganization(organizationID string, userID string) ([]*v1.Relationship, error) {
	if _, err := base64.StdEncoding.DecodeString(userID); err != nil {
		userID = base64.StdEncoding.EncodeToString([]byte(userID))
	}
	filter := v1.RelationshipFilter{
		ResourceType:          "organization",
		OptionalResourceId:    organizationID,
		OptionalSubjectFilter: &v1.SubjectFilter{SubjectType: "user", OptionalSubjectId: userID},
	}
	return m.GetRelationships(&filter)
}

func (m *DBRolesManager) GetUserOrgWorkspaces(organizationID string, userID string) ([]*v1.Relationship, error) {
	var relationships []*v1.Relationship
	userWorkspaceRelationships, err := m.GetUserRelationships(userID, "workspace")
	if err != nil {
		return relationships, err
	}
	orgWorkspaceRelationships, err := m.GetRelationshipsByOrganization(organizationID, "workspace")
	if err != nil {
		return relationships, err
	}
	orgWorkspaceMap := make(map[string]bool)
	for _, rel := range orgWorkspaceRelationships {
		orgWorkspaceMap[rel.Resource.ObjectId] = true
	}
	if len(orgWorkspaceMap) == 0 {
		logger.Warnf("no workspace->organization relations found for organization %s, falling back to direct workspace roles", organizationID)
		return userWorkspaceRelationships, nil
	}
	for _, rel := range userWorkspaceRelationships {
		if orgWorkspaceMap[rel.Resource.ObjectId] {
			relationships = append(relationships, rel)
		}
	}
	return relationships, nil
}

func (m *DBRolesManager) GetUserOrgProjects(organizationID string, userID string, orgWorkspaceRelationships []*v1.Relationship) ([]*v1.Relationship, error) {
	var relationships []*v1.Relationship
	userProjectRelationships, err := m.GetUserRelationships(userID, "project")
	if err != nil {
		return relationships, err
	}
	filter := v1.RelationshipFilter{ResourceType: "project", OptionalSubjectFilter: &v1.SubjectFilter{SubjectType: "workspace"}}
	workspaceProjectRelationships, err := m.GetRelationships(&filter)
	if err != nil {
		return relationships, err
	}
	orgWorkspaceMap := make(map[string]bool)
	for _, rel := range orgWorkspaceRelationships {
		orgWorkspaceMap[rel.Resource.ObjectId] = true
	}
	var orgProjectRelationships []*v1.Relationship
	for _, rel := range workspaceProjectRelationships {
		if orgWorkspaceMap[rel.Subject.Object.ObjectId] {
			orgProjectRelationships = append(orgProjectRelationships, rel)
		}
	}
	userProjectMap := make(map[string]*v1.Relationship)
	for _, rel := range userProjectRelationships {
		userProjectMap[rel.Resource.ObjectId] = rel
	}
	for _, rel := range orgProjectRelationships {
		if userRel, exists := userProjectMap[rel.Resource.ObjectId]; exists {
			relationships = append(relationships, userRel)
		}
	}
	return relationships, nil
}

func (m *DBRolesManager) GetUserAllRelationshipsByOrganization(organizationID string, userID string) ([]*v1.Relationship, error) {
	var relationships []*v1.Relationship
	orgRelationships, err := m.GetUserOrganization(organizationID, userID)
	if err != nil {
		return relationships, err
	}
	relationships = append(relationships, orgRelationships...)
	workspaceRelationships, err := m.GetUserOrgWorkspaces(organizationID, userID)
	if err != nil {
		return relationships, err
	}
	relationships = append(relationships, workspaceRelationships...)
	projectRelationships, err := m.GetUserOrgProjects(organizationID, userID, workspaceRelationships)
	if err != nil {
		return relationships, err
	}
	relationships = append(relationships, projectRelationships...)
	return relationships, nil
}

func (m *DBRolesManager) GetAdminSubjectUsers() ([]string, error) {
	filter := v1.RelationshipFilter{ResourceType: "user_directory", OptionalResourceId: "global", OptionalRelation: "admin"}
	relationships, err := m.GetRelationships(&filter)
	if err != nil {
		return nil, err
	}
	adminUsers := make([]string, 0, len(relationships))
	for _, rel := range relationships {
		adminUsers = append(adminUsers, rel.Subject.Object.ObjectId)
	}
	return adminUsers, nil
}
