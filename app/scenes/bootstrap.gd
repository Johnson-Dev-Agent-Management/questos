extends Node3D
## Stationary P1 scene. Physical input/launch/exit remain owner-tested.

const RAY_LENGTH := 5.0
const BASE_COLOR := Color(0.22, 0.8, 0.67)
const SELECTED_COLOR := Color(1.0, 0.55, 0.15)
var selected := false
var xr: OpenXRInterface
@onready var cube_material: StandardMaterial3D = $Cube.mesh.material


func _ready() -> void:
	xr = XRServer.find_interface("OpenXR")
	if xr != null and xr.is_initialized():
		get_viewport().use_xr = true
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	for controller: XRController3D in [$Origin/Left, $Origin/Right]:
		controller.button_pressed.connect(_on_button_pressed.bind(controller))
		controller.visible = false


func _physics_process(_delta: float) -> void:
	for controller: XRController3D in [$Origin/Left, $Origin/Right]:
		controller.visible = _can_interact(controller)


func _can_interact(controller: XRController3D) -> bool:
	return xr != null and xr.is_initialized() and xr.get_session_state() == OpenXRInterface.SESSION_STATE_FOCUSED and controller.get_has_tracking_data()


func target_at(from: Vector3, direction: Vector3) -> Object:
	var query := PhysicsRayQueryParameters3D.create(from, from + direction.normalized() * RAY_LENGTH, 1)
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	return hit.get("collider")


func select_target(target: Object) -> void:
	if target == $Cube/Body:
		selected = not selected
		cube_material.albedo_color = SELECTED_COLOR if selected else BASE_COLOR
	elif target == $Exit/Body:
		get_tree().quit()


func _on_button_pressed(action: String, controller: XRController3D) -> void:
	if not _can_interact(controller):
		return
	if action == "exit":
		get_tree().quit()
	elif action == "select":
		select_target(target_at(controller.global_position, -controller.global_basis.z))


func _unhandled_key_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		get_tree().quit()
