# Published body capabilities (spec §21). Tristate fields use 0=unsupported,
# 1=supported, 2=experimental so "experimental" is never treated as "supported".
string body_id
string locomotion_type       # biped|differential|omni|tracked|stationary|manipulator

uint8 walk
uint8 roll
uint8 reverse
uint8 turn_in_place
uint8 stairs
float32 maximum_speed_mps

bool front_camera
bool rear_camera
bool lidar_2d
bool lidar_3d
bool microphones

bool left_arm
bool right_arm
bool grippers
float32 maximum_payload_kg

uint8 UNSUPPORTED=0
uint8 SUPPORTED=1
uint8 EXPERIMENTAL=2
