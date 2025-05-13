---
id: create-a-project
title: Create a Project
description: Learn how to create a project using the REST API.
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Create a Project

:::info[Note]
Ensure that all [Prerequisites](./prerequisites.md) are met and that you have [obtained workspace and organization IDs](./obtain-ids.md) before proceeding with this tutorial.
:::

To create a project in the workspace, the [Intel® Geti™ REST API documentation](/docs/rest-api/openapi-specification#tag/projects/POST/organizations/{organization_id}/workspaces/{workspace_id}/projects) specifies that a `POST` request must be sent to the `/organizations/{organization_id}/workspaces/{workspace_id}/projects` endpoint. The endpoint description includes the message schema, lists available project types, and outlines constraints on the label configuration within the project. Currently, Intel® Geti™ supports projects with a single deep learning task or two tasks in a chain (e.g., Detection -> Classification or Detection -> Segmentation).
The request body must include the **project name** and **pipeline configuration**.

## Pipeline Configuration
**Pipeline configuration** is a JSON object that describes the task execution graph. It consists of:
- A list of tasks in the project,
- Labels for those tasks,
- Connections between the tasks.

1. The first task is of the `dataset` type, and all projects in Intel® Geti™ begin with this task. It represents the training dataset retrieval and preparation for model training.

2. The second task is the type of project you want to create. This task has a trainable model behind it. Below is the full list of currently supported trainable tasks:
  - `classification`
  - `detection`
  - `segmentation`
  - `rotated_detection`
  - `instance_segmentation`
  - `anomaly`
  - `keypoint_detection`

3. For a task chain project, you will need to define a crop task between the two tasks, as shown in the example below.

4. A default label indicating the lack of a match (e.g., the 'No object' label for Detection) is automatically created, so there is no need to create it manually.

5. Finally, the `connections` field is a list of dictionaries, where each dictionary contains the `from` and `to` keys, pointing to the IDs of the tasks in the pipeline configuration list. For a task chain project, you will need to define a connection between chained tasks through the crop task between the two tasks, as shown below.

<Tabs>
  <TabItem value="detection" label="Detection Bounding Box">
    ```python title="create-a-project.py" showLineNumbers
    project_name = "VEHICLE DETECTION PROJECT"
    tasks = [
      {
        "task_type": "dataset",
        "title": "Dataset",
      },
      {
        "task_type": "detection",
        "title": "Detection Task",
        "labels": [
            {
                "name": "Vehicle", "color": "#ff0000", "group": "default_detection",
            },
        ],
      },
    ]
    connections = [
      {
        "from": "Dataset",
        "to": "Detection Task",
      },
    ]
    ```
  </TabItem>
  <TabItem value="classification" label="Classification Single Label">
    ```python title="create-a-project.py" showLineNumbers
    project_name = "Example Classification Project"
    tasks = [
      {
        "task_type": "dataset",
        "title": "Dataset"
      },
      {
        "labels": [
          {
            "color": "#0015ffff", "group": "species", "hotkey": "ctrl+5", "name": "horse"
          },
          {
            "color": "#00ffffff", "group": "species", "hotkey": "ctrl+6", "name": "donkey"
          },
          {
            "color": "#00aaaaff", "group": "saddle_state", "hotkey": "ctrl+7", "name": "saddled"
          },
          {
            "color": "#00aaffff", "group": "saddle_state", "hotkey": "ctrl+8", "name": "unsaddled"
          }
        ],
        "task_type": "classification",
        "title": "Sample Classification Task"
      }
    ]
    connections = [
      {
        "from": "Dataset",
        "to": "Sample Classification Task"
      }
    ]
    ```
  </TabItem>
  <TabItem value="hierarchical-classification" label="Hierarchical Classification">
    ```python title="create-a-project.py" showLineNumbers
    project_name = "Example Classification Project - Label Hierarchy"
    tasks = [
      {
        "task_type": "dataset",
        "title": "Dataset"
      },
      {
        "labels": [
          {
            "color": "#0015ddff", "hotkey": "", "name": "animal", "group": "living"
          },
          {
            "color": "#0015ffff", "group": "species", "hotkey": "ctrl+5", "name": "horse", "parent_id": "animal"
          },
          {
            "color": "#00ffffff", "group": "species", "hotkey": "ctrl+6", "name": "donkey", "parent_id": "animal"
          },
          {
            "color": "#00aaaaff", "group": "saddle_state", "hotkey": "ctrl+7", "name": "saddled"
          },
          {
            "color": "#00aaffff", "group": "saddle_state", "hotkey": "ctrl+8", "name": "unsaddled"
          }
        ],
        "task_type": "classification",
        "title": "Sample Classification Task"
      }
    ]
    connections = [
      {
        "from": "Dataset",
        "to": "Sample Classification Task"
      }
    ]
    ```
  </TabItem>
  <TabItem value="detection-classification" label="Detection -> Classification">
    ```python title="create-a-project.py" showLineNumbers
    project_name = "Example Chain Project"
    tasks = [
      {
        "task_type": "dataset",
        "title": "Dataset"
      },
      {
        "labels": [
          {
            "color": "#0015FFFF", "group": "default_detection", "hotkey": "ctrl+5", "name": "object"
          }
        ],
        "task_type": "detection",
        "title": "Sample Detection Task"
      },
      {
        "task_type": "crop",
        "title": "Crop Task"
      },
      {
        "labels": [
          {
            "color": "#0015FFFF", "group": "default_classification", "hotkey": "ctrl+6", "name": "rectangle"
          },
          {
            "color": "#7F000AFF", "group": "default_classification", "hotkey": "ctrl+7", "name": "circle"
          },
          {
            "color": "#15FF00FF", "group": "default_classification", "hotkey": "ctrl+8", "name": "triangle"
          }
        ],
        "task_type": "classification",
        "title": "Sample Classification Task"
      }
    ]
    connections = [
      {
        "from": "Dataset",
        "to": "Sample Detection Task"
      },
      {
        "from": "Sample Detection Task",
        "to": "Crop Task"
      },
      {
        "from": "Crop Task",
        "to": "Sample Classification Task"
      }
    ]
    ```
  </TabItem>
</Tabs>

## Compile the Message and Submit the Project Creation Request

Let's package all the message components into the request body and send it to the server.

```python title="create-a-project.py" showLineNumbers
project_creation_request_data = {
    "name": project_name,
    "pipeline": {
        "connections": connections,
        "tasks": tasks,
    },
}

response = requests.post(
    BASE_URL + "projects", headers=headers, json=project_creation_request_data, verify=certifi.where()
)
project_dict = response.json()
```

Review the server's response. The server assigns `IDs` to all entities in the project, including the project itself, tasks, and labels. These IDs will be required to modify task configurations, assign labels to media items, and manage model deployments, among other operations.

Additionally, note that the server creates a default training dataset for the project.

<Tabs>
  <TabItem value="detection" label="Detection Bounding Box">
    ```json
    {
      "id": "{your_project_id}",
      "name": "TUTORIAL DETECTION PROJECT",
      "creation_time": "2024-07-03T17:35:28.896000+00:00",
      "creator_id": "{your_user_id}",
      "pipeline": {
        "tasks": [
          {
            "id": "{dataset_task_id}",
            "title": "Dataset",
            "task_type": "dataset"
          },
          {
            "id": "{detection_task_id}",
            "title": "Detection Task",
            "task_type": "detection",
            "labels": [
              {
                "id": "{object_label_id}",
                "name": "object",
                "is_anomalous": false,
                "color": "#ff0000ff",
                "hotkey": "",
                "is_empty": false,
                "group": "default_detection",
                "parent_id": null
              },
              {
                "id": "{no_object_label_id}",
                "name": "No object",
                "is_anomalous": false,
                "color": "#000000ff",
                "hotkey": "",
                "is_empty": true,
                "group": "No object",
                "parent_id": null
              }
            ],
            "label_schema_id": "{label_schema_id}"
          }
        ],
        "connections": [
          {
            "from": "{dataset_task_id}",
            "to": "{detection_task_id}"
          }
        ]
      },
      "thumbnail": "/api/v1/organizations/{your_org_id}/workspaces/{your_workspace_id}/projects/{your_project_id}/thumbnail",
      "performance": {
        "score": null,
        "task_performances": [
          {
            "task_id": "{detection_task_id}",
            "score": null
          }
        ]
      },
      "storage_info": {},
      "datasets": [
        {
          "id": "{dataset_id}",
          "name": "Dataset",
          "use_for_training": true,
          "creation_time": "2024-07-03T17:35:28.892000+00:00"
        }
      ]
    }
    ```
  </TabItem>
  <TabItem value="classification" label="Classification Single Label">
    ```json
    {
      "id": "{your_project_id}",
      "name": "Example Classification Project",
      "creation_time": "2021-07-28T09:37:17.319000+00:00",
      "creator_id": "{your_user_id}",
      "pipeline": {
        "connections": [
          {
            "from": "{dataset_task_id}",
            "to": "{classification_task_id}"
          }
        ],
        "tasks": [
          {
            "id": "{dataset_task_id}",
            "task_type": "dataset",
            "title": "Dataset"
          },
          {
            "id": "{classification_task_id}",
            "label_schema_id": "{label_schema_id}",
            "labels": [
              {
                "color": "#0015ffff",
                "group": "species",
                "hotkey": "ctrl+5",
                "id": "{horse_label_id}",
                "parent_id": null,
                "is_empty": false,
                "is_anomalous": false,
                "name": "horse"
              },
              {
                "color": "#00ffffff",
                "group": "species",
                "hotkey": "ctrl+6",
                "id": "{donkey_label_id}",
                "parent_id": null,
                "is_empty": false,
                "is_anomalous": false,
                "name": "donkey"
              },
              {
                "color": "#00aaaaff",
                "group": "saddle_state",
                "hotkey": "ctrl+7",
                "id": "{saddled_label_id}",
                "parent_id": null,
                "is_empty": false,
                "is_anomalous": false,
                "name": "saddled"
              },
              {
                "color": "#00aaffff",
                "group": "saddle_state",
                "hotkey": "ctrl+8",
                "id": "{unsaddled_label_id}",
                "parent_id": null,
                "is_empty": false,
                "is_anomalous": false,
                "name": "unsaddled"
              },
              {
                "color": "#7ada55ff",
                "group": "No class",
                "hotkey": "ctrl+0",
                "id": "{no_class_label_id}",
                "parent_id": null,
                "is_empty": true,
                "is_anomalous": false,
                "name": "No class"
              }
            ],
            "task_type": "classification",
            "title": "Sample Classification Task"
          }
        ]
      },
      "datasets": [
        {
          "id": "{dataset_task_id}",
          "name": "Example Classification Project",
          "creation_time": "2022-10-24T11:21:50.030000+00:00",
          "use_for_training": true
        }
      ],
      "storage_info": {},
      "performance": {
        "score": null,
        "task_performances": [
          {
            "task_id": "{classification_task_id}",
            "score": null
          }
        ]
      },
      "thumbnail": "/api/v1/organizations/{your_org_id}/workspaces/{your_workspace_id}/projects/{your_project_id}/thumbnail"
    }
    ```
  </TabItem>
  <TabItem value="hierarchical-classification" label="Hierarchical Classification">
    ```json
    {
      "id": "{your_project_id}",
      "name": "Example Classification Project - Label Hierarchy",
      "creation_time": "2021-07-28T10:09:31.764000+00:00",
      "creator_id": "{your_user_id}",
      "pipeline": {
        "connections": [
          {
            "from": "{dataset_task_id}",
            "to": "{classification_task_id}"
          }
        ],
        "tasks": [
          {
            "id": "{dataset_task_id}",
            "task_type": "dataset",
            "title": "Dataset"
          },
          {
            "id": "{classification_task_id}",
            "label_schema_id": "{label_schema_id}",
            "labels": [
              {
                "color": "#0015ddff",
                "group": "default - Sample Classification Task",
                "hotkey": "",
                "id": "{animal_label_id}",
                "parent_id": null,
                "is_empty": false,
                "is_anomalous": false,
                "name": "animal"
              },
              {
                "color": "#0015ffff",
                "group": "species",
                "hotkey": "ctrl+5",
                "id": "{horse_label_id}",
                "parent_id": "{animal_label_id}",
                "is_empty": false,
                "is_anomalous": false,
                "name": "horse"
              },
              {
                "color": "#00ffffff",
                "group": "species",
                "hotkey": "ctrl+6",
                "id": "{donkey_label_id}",
                "parent_id": "{animal_label_id}",
                "is_empty": false,
                "is_anomalous": false,
                "name": "donkey"
              },
              {
                "color": "#00aaaaff",
                "group": "saddle_state",
                "hotkey": "ctrl+7",
                "id": "{saddled_label_id}",
                "parent_id": null,
                "is_empty": false,
                "is_anomalous": false,
                "name": "saddled"
              },
              {
                "color": "#00aaffff",
                "group": "saddle_state",
                "hotkey": "ctrl+8",
                "id": "{unsaddled_label_id}",
                "parent_id": null,
                "is_empty": false,
                "is_anomalous": false,
                "name": "unsaddled"
              },
              {
                "color": "#9ee8d3ff",
                "group": "No class",
                "hotkey": "ctrl+0",
                "id": "{no_class_label_id}",
                "parent_id": null,
                "is_empty": true,
                "is_anomalous": false,
                "name": "No class"
              }
            ],
            "task_type": "classification",
            "title": "Sample Classification Task"
          }
        ]
      },
      "datasets": [
        {
          "id": "{dataset_task_id}",
          "name": "Example Classification Project",
          "creation_time": "2022-10-24T11:21:50.030000+00:00",
          "use_for_training": true
        }
      ],
      "storage_info": {},
      "performance": {
        "score": null,
        "task_performances": [
          {
            "task_id": "{classification_task_id}",
            "score": null
          }
        ]
      },
      "thumbnail": "/api/v1/organizations/{your_org_id}/workspaces/{your_workspace_id}/projects/{your_project_id}/thumbnail"
    }
    ```
  </TabItem>
  <TabItem value="detection-classification" label="Detection -> Classification">
    ```json
   {
      "id": "{your_project_id}",
      "name": "Example Chain Project",
      "creation_time": "2021-06-29T16:24:30.928000+00:00",
      "creator_id": "{your_user_id}",
      "datasets": [
        {
          "id": "{dataset_task_id}",
          "name": "Example Chain Project",
          "creation_time": "2022-10-24T11:21:50.030000+00:00",
          "use_for_training": true
        }
      ],
      "storage_info": {},
      "pipeline": {
        "connections": [
          {
            "from": "{dataset_task_id}",
            "to": "{detection_task_id}"
          },
          {
            "from": "{detection_task_id}",
            "to": "{crop_task_id}"
          },
          {
            "from": "{crop_task_id}",
            "to": "{classification_task_id}"
          }
        ],
        "tasks": [
          {
            "id": "{dataset_task_id}",
            "task_type": "dataset",
            "title": "Dataset"
          },
          {
            "id": "{detection_task_id}",
            "label_schema_id": "{label_schema_id}",
            "labels": [
              {
                "color": "#0015ffff",
                "group": "default_detection",
                "hotkey": "ctrl+5",
                "id": "{object_label_id}",
                "parent_id": null,
                "is_empty": false,
                "is_deleted": false,
                "is_anomalous": false,
                "name": "object"
              },
              {
                "color": "#ea879cff",
                "group": "No object",
                "hotkey": "ctrl+0",
                "id": "{no_object_label_id}",
                "parent_id": null,
                "is_empty": true,
                "is_deleted": false,
                "is_anomalous": false,
                "name": "No object"
              }
            ],
            "task_type": "detection",
            "title": "Sample Detection Task"
          },
          {
            "id": "{crop_task_id}",
            "task_type": "crop",
            "title": "Crop Task"
          },
          {
            "id": "{classification_task_id}",
            "labels": [
              {
                "color": "#0015ffff",
                "group": "default_classification",
                "hotkey": "ctrl+6",
                "id": "{rectangle_label_id}",
                "is_empty": false,
                "is_deleted": false,
                "is_anomalous": false,
                "name": "rectangle",
                "parent_id": "{object_label_id}"
              },
              {
                "color": "#7f000aff",
                "group": "default_classification",
                "hotkey": "ctrl+7",
                "id": "{circle_label_id}",
                "is_empty": false,
                "is_deleted": false,
                "is_anomalous": false,
                "name": "circle",
                "parent_id": "{object_label_id}"
              },
              {
                "color": "#15ff00ff",
                "group": "default_classification",
                "hotkey": "ctrl+8",
                "id": "{triangle_label_id}",
                "is_empty": false,
                "is_deleted": false,
                "is_anomalous": false,
                "name": "triangle",
                "parent_id": "{object_label_id}"
              },
              {
                "color": "#a311f7ff",
                "group": "No class",
                "hotkey": "ctrl+0",
                "id": "{no_class_label_id}",
                "parent_id": null,
                "is_empty": true,
                "is_deleted": false,
                "is_anomalous": false,
                "name": "No class"
              }
            ],
            "task_type": "classification",
            "title": "Sample Classification Task"
          }
        ]
      },
      "performance": {
        "score": null,
        "task_performances": [
          {
            "task_id": "{detection_task_id}",
            "score": null
          },
          {
            "task_id": "{classification_task_id}",
            "score": null
          }
        ]
      },
      "thumbnail": "/api/v1/organizations/{your_org_id}/workspaces/{your_workspace_id}/projects/{your_project_id}/thumbnail"
    }
    ```
  </TabItem>
</Tabs>

The complete working script for creating a project can be found here: [create-a-project.py](./scripts/create_a_project.py)
