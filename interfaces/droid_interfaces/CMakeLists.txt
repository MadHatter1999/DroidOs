cmake_minimum_required(VERSION 3.8)
project(droid_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/BodyCapabilities.msg"
  "msg/DroidState.msg"
  "msg/SafetyState.msg"
  "msg/TaskStatus.msg"
  "msg/StructuredIntent.msg"
  "srv/GetStatus.srv"
  "srv/ValidateIntent.srv"
  "srv/SetBody.srv"
  "srv/CancelTask.srv"
  "action/ExecuteTask.action"
  "action/NavigateToNamedPlace.action"
  "action/InspectTarget.action"
  "action/Speak.action"
  DEPENDENCIES std_msgs geometry_msgs
)

ament_package()
