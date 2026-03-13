# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

from service_connection.smtp_client import SMTPClient


def test_smtp_client_compose_mode_uses_env(mocker):
    mocker.patch(
        "service_connection.smtp_client.os.getenv",
        side_effect=lambda k, d=None: {
            "DEPLOYMENT_MODE": "compose",
            "INVITATION_FROM_ADDRESS": "noreply@example.local",
            "INVITATION_FROM_NAME": "Geti Local",
            "SMTP_PORT": "1025",
            "SMTP_LOGIN": "",
            "SMTP_PASSWORD": "",
            "SMTP_HOST": "mailhog",
        }.get(k, d),
    )
    smtp_ssl_mock = mocker.patch("service_connection.smtp_client.SMTP_SSL")
    smtp_mock = mocker.patch("service_connection.smtp_client.SMTP")
    mocker.patch("service_connection.smtp_client.SMTPClient._connect_with_tls")

    client = SMTPClient()

    assert client.from_mail == "noreply@example.local"
    assert client.from_name == "Geti Local"
    assert client.smtp_port == 1025
    assert client.smtp_host == "mailhog"
    smtp_ssl_mock.assert_not_called()
    smtp_mock.assert_called_once_with(host="mailhog", port=1025)
