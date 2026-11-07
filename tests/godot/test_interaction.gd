extends SceneTree
## Real scene/physics checks without pretending to supply hardware tracking.
var failed := false


func require(value: bool, message: String) -> void:
	if not value:
		printerr(message)
		failed = true


func _initialize() -> void:
	call_deferred("check_scene")


func check_scene() -> void:
	var scene = load("res://scenes/bootstrap.tscn").instantiate()
	root.add_child(scene)
	await physics_frame
	await physics_frame
	var cube = scene.get_node("Cube/Body")
	var target = scene.target_at(Vector3(0, 1.25, 0), Vector3.FORWARD)
	require(target == cube, "Ray must hit the actual cube collider")
	scene.select_target(target)
	require(scene.selected and scene.cube_material.albedo_color == scene.SELECTED_COLOR, "Selection changes color")
	scene.select_target(target)
	require(not scene.selected and scene.cube_material.albedo_color == scene.BASE_COLOR, "Second selection restores baseline")
	require(scene.target_at(Vector3(0, 1.25, 4), Vector3.FORWARD) == null, "Ray is bounded to five metres")
	require(scene.target_at(Vector3.ZERO, Vector3.UP) == null, "Miss must not select")
	require(scene.target_at(Vector3(0, 0.8, 0), Vector3.FORWARD) == scene.get_node("Exit/Body"), "Exit has a selectable collider")
	var controller = scene.get_node("Origin/Right")
	scene._on_button_pressed("select", controller)
	require(not scene.selected, "Inactive/untracked input must be ignored")
	# Visibility may lag tracking/focus by one physics frame. It is not authority.
	controller.visible = true
	controller.position = Vector3(0, 1.25, 0)
	scene._on_button_pressed("select", controller)
	require(not scene.selected, "Stale visibility must not permit input without a current focused/tracked session")
	var map: OpenXRActionMap = load("res://input/quest_touch.tres")
	var profile = map.interaction_profiles[0]
	require(profile.interaction_profile_path == "/interaction_profiles/oculus/touch_controller", "Touch profile required")
	require(profile.bindings.size() == 6, "Both hands need aim, trigger and exit bindings")
	require(ClassDB.class_has_method("OpenXRInterface", "get_session_state"), "XR focus API exists")
	require(ClassDB.class_has_method("XRController3D", "get_has_tracking_data"), "Tracking API exists")
	scene.queue_free()
	await process_frame
	print("P1 scene/physics checks passed" if not failed else "P1 scene/physics checks failed")
	quit(1 if failed else 0)
