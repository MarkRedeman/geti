#!/bin/sh
set -eu

cwd="$(pwd)"
service_root=""
service_pythonpath=""

case "$cwd" in
/interactive_ai/services/auto_train*)
	service_root="/interactive_ai/services/auto_train"
	service_pythonpath="$service_root"
	;;
/interactive_ai/services/dataset_ie*)
	service_root="/interactive_ai/services/dataset_ie"
	service_pythonpath="$service_root"
	;;
/interactive_ai/services/director*)
	service_root="/interactive_ai/services/director"
	service_pythonpath="$service_root:$service_root/app"
	;;
/interactive_ai/services/jobs*)
	service_root="/interactive_ai/services/jobs"
	service_pythonpath="$service_root"
	;;
/interactive_ai/services/project_ie*)
	service_root="/interactive_ai/services/project_ie"
	service_pythonpath="$service_root"
	;;
/interactive_ai/services/resource*)
	service_root="/interactive_ai/services/resource"
	service_pythonpath="$service_root:$service_root/app"
	;;
/interactive_ai/services/visual_prompt*)
	service_root="/interactive_ai/services/visual_prompt"
	service_pythonpath="$service_root"
	;;
/interactive_ai/services/model_registration*)
	service_root="/interactive_ai/services/model_registration"
	service_pythonpath="$service_root"
	;;
esac

if [ -n "$service_root" ]; then
	export PATH="$service_root/.venv/bin:$PATH"
	export PYTHONPATH="$service_pythonpath"

	if [ "$#" -eq 0 ]; then
		case "$service_root" in
		/interactive_ai/services/jobs)
			set -- python microservice/rest/main.py
			;;
		*)
			set -- python main.py
			;;
		esac
	fi
fi

exec "$@"
