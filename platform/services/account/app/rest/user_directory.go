// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

package rest

import (
	"context"
	"crypto/rand"
	"crypto/sha512"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	"account_service/app/config"
	"account_service/app/models"

	"geti.com/account_service_grpc/pb"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"golang.org/x/crypto/pbkdf2"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"gorm.io/gorm"
)

const (
	idTokenUserBaseDN          = "dc=example,dc=org"
	invitationPasswordB64      = "QFNDQWRtaW4="
	jwtSecretEnvVar            = "GETI_SECRET_IMPT_JWT_CONFIG_KEY"
	inviteExpirationEnvVar     = "GETI_CM_IMPT_CONFIGURATION_INVITE_USER_EXPIRATION"
	passwordResetExpirationEnv = "GETI_CM_IMPT_CONFIGURATION_PASSWORD_RESET_EXPIRATION"
)

type createUserBody struct {
	Email      string       `json:"email"`
	FirstName  string       `json:"firstName"`
	SecondName string       `json:"secondName"`
	Password   string       `json:"password"`
	Roles      []roleCreate `json:"roles"`
}

type roleCreate struct {
	Role         string `json:"role"`
	ResourceType string `json:"resourceType"`
	ResourceID   string `json:"resourceId"`
}

type inviteUserRequest struct {
	User  inviteUserData `json:"user"`
	Roles []roleOpBody   `json:"roles"`
}

type inviteUserData struct {
	Email          string `json:"email"`
	OrganizationID string `json:"organizationId"`
	FirstName      string `json:"firstName"`
	SecondName     string `json:"secondName"`
}

type roleOpBody struct {
	Role      roleCreate `json:"role"`
	Operation string     `json:"operation"`
}

type passwordRequestResetBody struct {
	Email string `json:"email"`
}

type passwordResetBody struct {
	Token       string `json:"token"`
	NewPassword string `json:"new_password"`
}

type activateBody struct {
	FirstName  string `json:"first_name"`
	SecondName string `json:"second_name"`
	Password   string `json:"password"`
	Token      string `json:"token"`
}

type updatePasswordBody struct {
	NewPassword string `json:"new_password"`
	OldPassword string `json:"old_password"`
}

type credentialUser struct {
	UID        string
	Mail       string
	Name       string
	Password   string
	EmailToken string
	Registered bool
}

type credentialsBackend struct{}

var userDirectoryDB *gorm.DB

func SetDB(db *gorm.DB) {
	userDirectoryDB = db
}

func HandleCreateOrganizationUser(w http.ResponseWriter, r *http.Request, pathParams map[string]string) {
	var (
		createdUserID          string
		organizationID         string
		credentialsBackendSafe *credentialsBackend
	)
	defer func() {
		if recovered := recover(); recovered != nil {
			logger.Errorf("panic while handling create organization user: %v", recovered)
			if createdUserID != "" && organizationID != "" {
				rollbackCreatedAccountUser(createdUserID, organizationID)
			}
			if credentialsBackendSafe != nil && createdUserID != "" {
				_ = deleteCredentialUser(credentialsBackendSafe, createdUserID)
			}
			http.Error(w, "unexpected error", http.StatusInternalServerError)
		}
	}()

	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	organizationID = pathParams["organization_id"]
	if organizationID == "" {
		http.Error(w, "organization_id missing", http.StatusBadRequest)
		return
	}

	var body createUserBody
	if err := decodeJSONBody(r, &body); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	conn, err := grpc.Dial(config.GrpcServerAddress, grpc.WithTransportCredentials(insecure.NewCredentials())) //nolint:all
	if err != nil {
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	defer conn.Close() //nolint:errcheck

	userClient := pb.NewUserClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), grpcRequestTimeout)
	defer cancel()

	createdUser, err := userClient.Create(ctx, &pb.UserData{
		FirstName:      body.FirstName,
		SecondName:     body.SecondName,
		Email:          body.Email,
		Status:         "ACT",
		OrganizationId: organizationID,
		ExternalId:     "default",
	})
	if err != nil {
		writeGRPCError(w, err)
		return
	}
	createdUserID = createdUser.Id

	credentialsBackendConn, err := connectCredentialsBackend()
	if err != nil {
		_, _ = userClient.Delete(ctx, &pb.UserIdRequest{UserId: createdUser.Id, OrganizationId: organizationID})
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	credentialsBackendSafe = credentialsBackendConn
	if credentialsBackendConn != nil {
		defer credentialsBackendConn.Close()
	}

	if err = createCredentialUser(credentialsBackendConn, createdUser.Id, body.Email, body.FirstName, body.Password, true, true); err != nil {
		_, _ = userClient.Delete(ctx, &pb.UserIdRequest{UserId: createdUser.Id, OrganizationId: organizationID})
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	roleOps := make([]*pb.UserRoleOperation, 0, len(body.Roles))
	for _, role := range body.Roles {
		roleOps = append(roleOps, &pb.UserRoleOperation{
			Role:      &pb.UserRole{Role: role.Role, ResourceType: role.ResourceType, ResourceId: role.ResourceID},
			Operation: "CREATE",
		})
	}

	if len(roleOps) > 0 {
		_, err = userClient.SetRoles(ctx, &pb.UserRolesRequest{Roles: roleOps, UserId: createdUser.Id, OrganizationId: organizationID})
		if err != nil {
			_, _ = userClient.Delete(ctx, &pb.UserIdRequest{UserId: createdUser.Id, OrganizationId: organizationID})
			_ = deleteCredentialUser(credentialsBackendConn, createdUser.Id)
			writeGRPCError(w, err)
			return
		}
	}

	sub := encodeIDTokenSubject(createdUser.Id)
	createdUser.ExternalId = sub
	updatedUser, err := userClient.Modify(ctx, createdUser)
	if err != nil {
		_, _ = userClient.Delete(ctx, &pb.UserIdRequest{UserId: createdUser.Id, OrganizationId: organizationID})
		_ = deleteCredentialUser(credentialsBackendConn, createdUser.Id)
		writeGRPCError(w, err)
		return
	}

	updatedUser.Roles = make([]*pb.UserRole, 0, len(body.Roles))
	for _, role := range body.Roles {
		updatedUser.Roles = append(updatedUser.Roles, &pb.UserRole{
			Role: role.Role, ResourceType: role.ResourceType, ResourceId: role.ResourceID,
		})
	}

	writeJSON(w, http.StatusCreated, updatedUser)
}

func HandleInviteUser(w http.ResponseWriter, r *http.Request, pathParams map[string]string) {
	var (
		createdUserID          string
		organizationID         string
		credentialsBackendSafe *credentialsBackend
	)
	defer func() {
		if recovered := recover(); recovered != nil {
			logger.Errorf("panic while handling invite user: %v", recovered)
			if createdUserID != "" && organizationID != "" {
				rollbackCreatedAccountUser(createdUserID, organizationID)
			}
			if credentialsBackendSafe != nil && createdUserID != "" {
				_ = deleteCredentialUser(credentialsBackendSafe, createdUserID)
			}
			http.Error(w, "unexpected error", http.StatusInternalServerError)
		}
	}()

	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	organizationID = pathParams["organization_id"]
	if organizationID == "" {
		http.Error(w, "organization_id missing", http.StatusBadRequest)
		return
	}

	var body inviteUserRequest
	if err := decodeJSONBody(r, &body); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	conn, err := grpc.Dial(config.GrpcServerAddress, grpc.WithTransportCredentials(insecure.NewCredentials())) //nolint:all
	if err != nil {
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	defer conn.Close() //nolint:errcheck

	userClient := pb.NewUserClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), grpcRequestTimeout)
	defer cancel()

	createdUser, err := userClient.Create(ctx, &pb.UserData{
		FirstName:      body.User.FirstName,
		SecondName:     body.User.SecondName,
		Email:          body.User.Email,
		Status:         "RGS",
		OrganizationId: organizationID,
		ExternalId:     "default",
	})
	if err != nil {
		writeGRPCError(w, err)
		return
	}
	createdUserID = createdUser.Id

	credentialsBackendConn, err := connectCredentialsBackend()
	if err != nil {
		_, _ = userClient.Delete(ctx, &pb.UserIdRequest{UserId: createdUser.Id, OrganizationId: organizationID})
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	credentialsBackendSafe = credentialsBackendConn
	if credentialsBackendConn != nil {
		defer credentialsBackendConn.Close()
	}

	if err = createCredentialUser(credentialsBackendConn, createdUser.Id, body.User.Email, body.User.FirstName, invitationPasswordB64, true, true); err != nil {
		_, _ = userClient.Delete(ctx, &pb.UserIdRequest{UserId: createdUser.Id, OrganizationId: organizationID})
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	roleOps := make([]*pb.UserRoleOperation, 0, len(body.Roles))
	for _, role := range body.Roles {
		roleOps = append(roleOps, &pb.UserRoleOperation{
			Role:      &pb.UserRole{Role: role.Role.Role, ResourceType: role.Role.ResourceType, ResourceId: role.Role.ResourceID},
			Operation: role.Operation,
		})
	}
	if len(roleOps) > 0 {
		_, err = userClient.SetRoles(ctx, &pb.UserRolesRequest{Roles: roleOps, UserId: createdUser.Id, OrganizationId: organizationID})
		if err != nil {
			_, _ = userClient.Delete(ctx, &pb.UserIdRequest{UserId: createdUser.Id, OrganizationId: organizationID})
			_ = deleteCredentialUser(credentialsBackendConn, createdUser.Id)
			writeGRPCError(w, err)
			return
		}
	}

	sub := encodeIDTokenSubject(createdUser.Id)
	createdUser.ExternalId = sub
	_, err = userClient.Modify(ctx, createdUser)
	if err != nil {
		_, _ = userClient.Delete(ctx, &pb.UserIdRequest{UserId: createdUser.Id, OrganizationId: organizationID})
		_ = deleteCredentialUser(credentialsBackendConn, createdUser.Id)
		writeGRPCError(w, err)
		return
	}

	inviteExpirationMinutes := getEnvAsInt(inviteExpirationEnvVar, 60)
	secret := getJWTSecret()
	if secret != "" {
		token, tokenErr := generateAndStoreCredentialToken(credentialsBackendConn, createdUser.Id, body.User.Email, secret, inviteExpirationMinutes)
		if tokenErr != nil {
			logger.Warnf("failed to create invitation token: %v", tokenErr)
		} else {
			logger.Infof("invitation token generated for user %s (email dispatch disabled in compose)", createdUser.Id)
			_ = token
		}
	}

	w.WriteHeader(http.StatusCreated)
}

func HandleRequestPasswordReset(w http.ResponseWriter, r *http.Request, _ map[string]string) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var body passwordRequestResetBody
	if err := decodeJSONBody(r, &body); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	credentialsBackendConn, err := connectCredentialsBackend()
	if err != nil {
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	if credentialsBackendConn != nil {
		defer credentialsBackendConn.Close()
	}

	user, err := getCredentialUserByMail(credentialsBackendConn, body.Email)
	if err == nil {
		secret := getJWTSecret()
		if secret != "" {
			_, tokenErr := generateAndStoreCredentialToken(credentialsBackendConn, user.UID, user.Mail, secret, getEnvAsInt(passwordResetExpirationEnv, 60))
			if tokenErr != nil {
				logger.Warnf("failed to create password reset token: %v", tokenErr)
			}
		}
	}

	writePlain(w, http.StatusAccepted, "Password reset request sent")
}

func HandleResetPassword(w http.ResponseWriter, r *http.Request, _ map[string]string) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var body passwordResetBody
	if err := decodeJSONBody(r, &body); err != nil {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	secret := getJWTSecret()
	if secret == "" {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	uid, _, err := verifyServiceJWT(body.Token, secret)
	if err != nil {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	credentialsBackendConn, err := connectCredentialsBackend()
	if err != nil {
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	if credentialsBackendConn != nil {
		defer credentialsBackendConn.Close()
	}

	user, err := getCredentialUserByUID(credentialsBackendConn, uid)
	if err != nil || user.EmailToken != body.Token {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	if err = updateCredentialPassword(credentialsBackendConn, uid, body.NewPassword); err != nil {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}
	_ = updateCredentialEmailToken(credentialsBackendConn, uid, "")

	writePlain(w, http.StatusOK, "Password was reset")
}

func HandleConfirmRegistration(w http.ResponseWriter, r *http.Request, _ map[string]string) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var body activateBody
	if err := decodeJSONBody(r, &body); err != nil {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	secret := getJWTSecret()
	if secret == "" {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	uid, mail, err := verifyServiceJWT(body.Token, secret)
	if err != nil {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	credentialsBackendConn, err := connectCredentialsBackend()
	if err != nil {
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	if credentialsBackendConn != nil {
		defer credentialsBackendConn.Close()
	}

	user, err := getCredentialUserByUID(credentialsBackendConn, uid)
	if err != nil || user.EmailToken != body.Token {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}

	conn, err := grpc.Dial(config.GrpcServerAddress, grpc.WithTransportCredentials(insecure.NewCredentials())) //nolint:all
	if err != nil {
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	defer conn.Close() //nolint:errcheck

	userClient := pb.NewUserClient(conn)
	orgClient := pb.NewOrganizationClient(conn)
	statusClient := pb.NewUserStatusClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), grpcRequestTimeout)
	defer cancel()

	orgs, err := orgClient.Find(ctx, &pb.FindOrganizationRequest{})
	if err != nil || len(orgs.Organizations) == 0 {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}
	organizationID := orgs.Organizations[0].Id

	users, err := userClient.Find(ctx, &pb.FindUserRequest{Email: mail, OrganizationId: organizationID})
	if err != nil || len(users.Users) == 0 {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}
	userData := users.Users[0]

	_, err = userClient.Modify(ctx, &pb.UserData{
		Id:             userData.Id,
		OrganizationId: organizationID,
		FirstName:      body.FirstName,
		SecondName:     body.SecondName,
		Email:          userData.Email,
		ExternalId:     userData.ExternalId,
		Country:        userData.Country,
		Status:         "ACT",
	})
	if err != nil {
		writeGRPCError(w, err)
		return
	}

	_, err = statusClient.Change(ctx, &pb.UserStatusRequest{Status: "ACT", UserId: userData.Id, OrganizationId: organizationID})
	if err != nil {
		writeGRPCError(w, err)
		return
	}

	if err = updateCredentialPassword(credentialsBackendConn, uid, body.Password); err != nil {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}
	_ = updateCredentialEmailToken(credentialsBackendConn, uid, "")

	w.WriteHeader(http.StatusOK)
}

func HandleUpdatePassword(w http.ResponseWriter, r *http.Request, pathParams map[string]string) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	userID := pathParams["user_id"]
	if userID == "" {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	var body updatePasswordBody
	if err := decodeJSONBody(r, &body); err != nil {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	callerID := extractUserIDFromForwardedToken(r.Header.Get("x-auth-request-access-token"))
	if callerID == "" || callerID != userID {
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	credentialsBackendConn, err := connectCredentialsBackend()
	if err != nil {
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	if credentialsBackendConn != nil {
		defer credentialsBackendConn.Close()
	}

	user, err := getCredentialUserByUID(credentialsBackendConn, userID)
	if err != nil {
		http.Error(w, "User not found", http.StatusNotFound)
		return
	}

	if err = validateOldPassword(user.Password, body.OldPassword); err != nil {
		writePlain(w, http.StatusBadRequest, "Wrong old password")
		return
	}

	if body.OldPassword == body.NewPassword {
		writePlain(w, http.StatusConflict, "Old and new password cannot be same")
		return
	}

	if err = updateCredentialPassword(credentialsBackendConn, userID, body.NewPassword); err != nil {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	writePlain(w, http.StatusOK, "Password has been updated")
}

func HandleUsersCount(w http.ResponseWriter, r *http.Request, _ map[string]string) {
	if r.Method != http.MethodGet {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	conn, err := grpc.Dial(config.GrpcServerAddress, grpc.WithTransportCredentials(insecure.NewCredentials())) //nolint:all
	if err != nil {
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}
	defer conn.Close() //nolint:errcheck

	orgClient := pb.NewOrganizationClient(conn)
	userClient := pb.NewUserClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), grpcRequestTimeout)
	defer cancel()

	orgs, err := orgClient.Find(ctx, &pb.FindOrganizationRequest{})
	if err != nil || len(orgs.Organizations) == 0 {
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	users, err := userClient.Find(ctx, &pb.FindUserRequest{OrganizationId: orgs.Organizations[0].Id})
	if err != nil {
		writeGRPCError(w, err)
		return
	}

	writePlain(w, http.StatusOK, fmt.Sprintf("%d", users.TotalMatchedCount))
}

func rollbackCreatedAccountUser(userID string, organizationID string) {
	conn, err := grpc.Dial(config.GrpcServerAddress, grpc.WithTransportCredentials(insecure.NewCredentials())) //nolint:all
	if err != nil {
		logger.Errorf("failed to initialize rollback connection: %v", err)
		return
	}
	defer conn.Close() //nolint:errcheck

	userClient := pb.NewUserClient(conn)
	ctx, cancel := context.WithTimeout(context.Background(), grpcRequestTimeout)
	defer cancel()

	_, err = userClient.Delete(ctx, &pb.UserIdRequest{UserId: userID, OrganizationId: organizationID})
	if err != nil {
		logger.Errorf("failed to rollback created account user %s: %v", userID, err)
	}
}

func writeGRPCError(w http.ResponseWriter, err error) {
	st, ok := status.FromError(err)
	if !ok {
		http.Error(w, "unexpected error", http.StatusInternalServerError)
		return
	}

	switch st.Code() {
	case codes.InvalidArgument:
		http.Error(w, st.Message(), http.StatusBadRequest)
	case codes.AlreadyExists:
		http.Error(w, st.Message(), http.StatusConflict)
	case codes.NotFound:
		http.Error(w, st.Message(), http.StatusNotFound)
	case codes.FailedPrecondition:
		http.Error(w, st.Message(), http.StatusConflict)
	default:
		http.Error(w, "unexpected error", http.StatusInternalServerError)
	}
}

func decodeJSONBody(r *http.Request, target interface{}) error {
	decoder := jsonDecoder(r)
	defer r.Body.Close()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	return nil
}

func jsonDecoder(r *http.Request) *json.Decoder {
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	return decoder
}

func writeJSON(w http.ResponseWriter, statusCode int, payload interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(payload)
}

func writePlain(w http.ResponseWriter, statusCode int, message string) {
	w.Header().Set("Content-Type", "text/plain")
	w.WriteHeader(statusCode)
	_, _ = w.Write([]byte(message))
}

func getJWTSecret() string {
	return os.Getenv(jwtSecretEnvVar)
}

func getEnvAsInt(name string, def int) int {
	raw := os.Getenv(name)
	if raw == "" {
		return def
	}
	parsed, err := strconv.Atoi(raw)
	if err != nil {
		return def
	}
	return parsed
}

func connectCredentialsBackend() (*credentialsBackend, error) {
	if userDirectoryDB == nil {
		return nil, errors.New("user directory db is not initialized")
	}
	return &credentialsBackend{}, nil
}

func (b *credentialsBackend) Close() {
}

func sqlCreateCredential(uid string, passwordB64 string, registered bool) error {
	if userDirectoryDB == nil {
		return errors.New("user directory db is not initialized")
	}

	userUUID, err := uuid.Parse(uid)
	if err != nil {
		return err
	}

	passwordDecoded, err := decodePassword(passwordB64)
	if err != nil {
		return err
	}
	if err = checkPasswordStrength(passwordDecoded); err != nil {
		return err
	}

	credential := models.UserCredential{}
	err = userDirectoryDB.Where("user_id = ?", userUUID).First(&credential).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		credential = models.UserCredential{
			UserID:       userUUID,
			PasswordHash: hashPassword(passwordDecoded),
			Registered:   registered,
		}
		return userDirectoryDB.Create(&credential).Error
	}
	if err != nil {
		return err
	}

	credential.PasswordHash = hashPassword(passwordDecoded)
	credential.Registered = registered
	return userDirectoryDB.Save(&credential).Error
}

func sqlGetUserByUID(uid string) (*credentialUser, error) {
	if userDirectoryDB == nil {
		return nil, errors.New("user directory db is not initialized")
	}

	userUUID, err := uuid.Parse(uid)
	if err != nil {
		return nil, err
	}

	userModel := models.User{}
	err = userDirectoryDB.Where("id = ?", userUUID).First(&userModel).Error
	if err != nil {
		return nil, err
	}

	credential := models.UserCredential{}
	err = userDirectoryDB.Where("user_id = ?", userUUID).First(&credential).Error
	if err != nil {
		return nil, err
	}

	return &credentialUser{
		UID:        userModel.ID.String(),
		Mail:       userModel.Email,
		Name:       userModel.FirstName,
		Password:   credential.PasswordHash,
		EmailToken: credential.EmailToken,
		Registered: credential.Registered,
	}, nil
}

func sqlGetUserByMail(mail string) (*credentialUser, error) {
	if userDirectoryDB == nil {
		return nil, errors.New("user directory db is not initialized")
	}

	userModel := models.User{}
	err := userDirectoryDB.Where("email = ?", mail).First(&userModel).Error
	if err != nil {
		return nil, err
	}

	return sqlGetUserByUID(userModel.ID.String())
}

func createCredentialUser(conn *credentialsBackend, uid string, mail string, name string, passwordB64 string, admin bool, registered bool) error {
	_ = conn
	_ = mail
	_ = name
	_ = admin
	return sqlCreateCredential(uid, passwordB64, registered)
}

func deleteCredentialUser(conn *credentialsBackend, uid string) error {
	_ = conn
	userUUID, err := uuid.Parse(uid)
	if err != nil {
		return err
	}
	return userDirectoryDB.Where("user_id = ?", userUUID).Delete(&models.UserCredential{}).Error
}

func getCredentialUserByUID(conn *credentialsBackend, uid string) (*credentialUser, error) {
	_ = conn
	return sqlGetUserByUID(uid)
}

func getCredentialUserByMail(conn *credentialsBackend, mail string) (*credentialUser, error) {
	_ = conn
	return sqlGetUserByMail(mail)
}

func updateCredentialPassword(conn *credentialsBackend, uid string, newPasswordB64 string) error {
	_ = conn
	passwordDecoded, err := decodePassword(newPasswordB64)
	if err != nil {
		return err
	}
	if err = checkPasswordStrength(passwordDecoded); err != nil {
		return err
	}
	userUUID, err := uuid.Parse(uid)
	if err != nil {
		return err
	}
	return userDirectoryDB.Model(&models.UserCredential{}).
		Where("user_id = ?", userUUID).
		Update("password_hash", hashPassword(passwordDecoded)).Error
}

func updateCredentialEmailToken(conn *credentialsBackend, uid string, token string) error {
	_ = conn
	userUUID, err := uuid.Parse(uid)
	if err != nil {
		return err
	}
	return userDirectoryDB.Model(&models.UserCredential{}).
		Where("user_id = ?", userUUID).
		Update("email_token", token).Error
}

func generateAndStoreCredentialToken(conn *credentialsBackend, uid string, mail string, secret string, expMinutes int) (string, error) {
	token, err := generateServiceJWT(uid, mail, secret, expMinutes)
	if err != nil {
		return "", err
	}
	if err = updateCredentialEmailToken(conn, uid, token); err != nil {
		return "", err
	}
	return token, nil
}

func generateServiceJWT(uid string, mail string, secret string, expMinutes int) (string, error) {
	claims := jwt.MapClaims{
		"uid":  uid,
		"mail": mail,
		"exp":  time.Now().UTC().Add(time.Duration(expMinutes) * time.Minute).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte(secret))
}

func verifyServiceJWT(tokenString string, secret string) (string, string, error) {
	claims := jwt.MapClaims{}
	_, err := jwt.ParseWithClaims(tokenString, claims, func(token *jwt.Token) (interface{}, error) {
		return []byte(secret), nil
	})
	if err != nil {
		return "", "", err
	}
	uid, _ := claims["uid"].(string)
	mail, _ := claims["mail"].(string)
	if uid == "" {
		return "", "", errors.New("missing uid")
	}
	return uid, mail, nil
}

func extractUserIDFromForwardedToken(tokenString string) string {
	claims := jwt.MapClaims{}
	_, err := jwt.ParseWithClaims(tokenString, claims, func(_ *jwt.Token) (interface{}, error) {
		return []byte("unused"), nil
	})
	if err != nil && !errors.Is(err, jwt.ErrTokenSignatureInvalid) {
		return ""
	}

	if ownerID, ok := claims["owner_id"].(string); ok && ownerID != "" {
		return ownerID
	}
	if preferred, ok := claims["preferred_username"].(string); ok {
		return preferred
	}
	return ""
}

func decodePassword(value string) ([]byte, error) {
	decoded, err := base64.RawURLEncoding.DecodeString(value)
	if err == nil {
		return decoded, nil
	}
	decoded, err = base64.URLEncoding.DecodeString(value)
	if err == nil {
		return decoded, nil
	}
	return nil, err
}

func checkPasswordStrength(decoded []byte) error {
	if len(decoded) < 8 || len(decoded) > 200 {
		return errors.New("weak password")
	}

	hasUpper := false
	hasLower := false
	hasDigit := false
	hasSymbol := false

	for _, ch := range decoded {
		if ch >= 'A' && ch <= 'Z' {
			hasUpper = true
			continue
		}
		if ch >= 'a' && ch <= 'z' {
			hasLower = true
			continue
		}
		if ch >= '0' && ch <= '9' {
			hasDigit = true
			continue
		}
		if ch >= 32 && ch <= 126 {
			hasSymbol = true
			continue
		}
		return errors.New("weak password")
	}

	if !hasUpper || !hasLower || (!hasDigit && !hasSymbol) {
		return errors.New("weak password")
	}

	return nil
}

func hashPassword(decoded []byte) string {
	salt := make([]byte, 16)
	_, _ = rand.Read(salt)
	iterations := 25000
	key := pbkdf2.Key(decoded, salt, iterations, 64, sha512.New)
	return fmt.Sprintf("{PBKDF2-SHA512}%d$%s$%s", iterations, ab64Encode(salt), ab64Encode(key))
}

func validateOldPassword(storedHash string, oldPasswordB64 string) error {
	decoded, err := decodePassword(oldPasswordB64)
	if err != nil {
		return err
	}

	partsRegexp := regexp.MustCompile(`^\{PBKDF2-SHA512\}(\d+)\$([^$]+)\$(.+)$`)
	matches := partsRegexp.FindStringSubmatch(storedHash)
	if len(matches) != 4 {
		return errors.New("invalid hash format")
	}

	iterations, err := strconv.Atoi(matches[1])
	if err != nil {
		return err
	}
	salt, err := ab64Decode(matches[2])
	if err != nil {
		return err
	}
	storedKey, err := ab64Decode(matches[3])
	if err != nil {
		return err
	}

	derived := pbkdf2.Key(decoded, salt, iterations, len(storedKey), sha512.New)
	if !constantTimeEqual(derived, storedKey) {
		return errors.New("wrong old password")
	}
	return nil
}

func ab64Encode(value []byte) string {
	encoded := base64.StdEncoding.EncodeToString(value)
	encoded = strings.TrimRight(encoded, "=")
	return strings.ReplaceAll(encoded, "+", ".")
}

func ab64Decode(value string) ([]byte, error) {
	converted := strings.ReplaceAll(value, ".", "+")
	for len(converted)%4 != 0 {
		converted += "="
	}
	return base64.StdEncoding.DecodeString(converted)
}

func constantTimeEqual(a []byte, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	var result byte
	for idx := range a {
		result |= a[idx] ^ b[idx]
	}
	return result == 0
}

func encodeIDTokenSubject(uid string) string {
	userID := fmt.Sprintf("cn=%s,%s", uid, idTokenUserBaseDN)
	connID := "regular_users"

	message := make([]byte, 0, len(userID)+len(connID)+4)
	message = appendProtoStringField(message, 1, userID)
	message = appendProtoStringField(message, 2, connID)

	encoded := base64.StdEncoding.EncodeToString(message)
	return strings.TrimRight(encoded, "=")
}

func appendProtoStringField(buffer []byte, fieldNumber int, value string) []byte {
	key := byte((fieldNumber << 3) | 2)
	buffer = append(buffer, key)
	buffer = appendVarint(buffer, uint64(len(value)))
	buffer = append(buffer, []byte(value)...)
	return buffer
}

func appendVarint(buffer []byte, value uint64) []byte {
	for value >= 0x80 {
		buffer = append(buffer, byte(value)|0x80)
		value >>= 7
	}
	buffer = append(buffer, byte(value))
	return buffer
}
