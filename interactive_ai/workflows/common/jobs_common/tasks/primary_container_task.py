# Copyright (C) 2022-2025 Intel Corporation
# LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

"""Compose-mode task decorators and pod-spec placeholders."""

import logging
import os
import threading
from collections.abc import Callable
from functools import wraps
from time import sleep

import requests
from geti_kafka_tools import terminate_producer
from geti_telemetry_tools import terminate_span_exporter

logger = logging.getLogger(__name__)

TERM_ISTIO_PROXY_URL = "http://127.0.0.1:15020/quitquitquit"


def get_pod_spec(
    resources: dict | None = None,
    node_selector: dict[str, str] | None = None,
    tolerations: list[dict] | None = None,
) -> dict:
    """Builds a pod-spec compatibility dictionary for compose mode."""
    return {
        "resources": resources,
        "node_selector": node_selector,
        "tolerations": tolerations,
    }


def _start_istio_termination(n_trials: int = 10, timeout: float = 1.0, sleep_sec: float = 1.0):
    logger.info("starting terminating the istio-proxy sidecar container")
    sleep(20)

    is_terminated = False
    for step in range(1, n_trials + 1):
        try:
            response = requests.post(TERM_ISTIO_PROXY_URL, timeout=timeout)

            if response.status_code == 200:
                is_terminated = True
                break
        except Exception as e:
            logger.warning("[%d/%d] Cannot terminate istio proxy: %s", step, n_trials, e)

        sleep(sleep_sec)

    if not is_terminated:
        logger.error("Cannot terminate istio proxy")


def _terminate_istio_proxy(n_trials: int = 10, timeout: float = 1.0, sleep_sec: float = 1.0):
    if "KUBERNETES_SERVICE_HOST" not in os.environ:
        logger.debug("Skipping istio-proxy termination outside Kubernetes")
        return

    # after upgrade of istio to 1.26.4 istio-proxy sidecar started to be closed too early - not allowing the main
    # process to store all required data in seaweed-fs. The only solution to postpone this operation - but without
    # blocking the main thread - appeared to be starting a separate thread that will try to terminate istio-proxy after
    # 20 seconds - allowing main thread to finish all its operations
    thread = threading.Thread(target=_start_istio_termination, args=(n_trials, timeout, sleep_sec))
    thread.daemon = False  # Ensure the thread doesn't exit when the main process exits
    thread.start()


def compose_task(  # noqa: ANN201
    _function: Callable | None = None,
    task_config: dict | None = None,
    pod_spec: dict | None = None,
    *args,
    **kwargs,
):
    """
    Decorates a compose-mode task function.

    :param task_config: Ignored in compose mode (kept for compatibility).
    :param pod_spec: Ignored in compose mode (kept for compatibility).
    """

    _ = (task_config, pod_spec, args, kwargs)

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            finally:
                terminate_producer()
                terminate_span_exporter()
                _terminate_istio_proxy()

        return wrapper

    if _function is not None:
        return decorator(_function)
    return decorator


def compose_dynamic(  # noqa: ANN201
    _function: Callable | None = None,
    task_config: dict | None = None,
    pod_spec: dict | None = None,
    *args,
    **kwargs,
):
    """
    Decorates a compose-mode dynamic function.

    :param task_config: Ignored in compose mode (kept for compatibility).
    :param pod_spec: Ignored in compose mode (kept for compatibility).
    """

    _ = (task_config, pod_spec, args, kwargs)

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            finally:
                terminate_producer()
                terminate_span_exporter()
                _terminate_istio_proxy()

        return wrapper

    if _function is not None:
        return decorator(_function)
    return decorator
