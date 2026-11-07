@tool
extends EditorPlugin

const QuestExport = preload("res://addons/quest_candidate/quest_export.gd")
var exporter: EditorExportPlugin


func _enter_tree() -> void:
	exporter = QuestExport.new()
	add_export_plugin(exporter)


func _exit_tree() -> void:
	remove_export_plugin(exporter)
