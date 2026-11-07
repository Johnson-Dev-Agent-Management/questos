@tool
extends EditorExportPlugin
## Manifest-only adapter. Godot supplies the Khronos loader and broker queries.


func _get_name() -> String:
	return "Quest2Candidate"


func _supports_platform(platform: EditorExportPlatform) -> bool:
	return platform is EditorExportPlatformAndroid


func _get_android_manifest_application_element_contents(_platform: EditorExportPlatform, _debug: bool) -> String:
	return """
        <meta-data android:name="com.oculus.supportedDevices" android:value="quest2" />
        <meta-data android:name="com.oculus.vr.focusaware" android:value="true" />
"""


func _get_android_manifest_activity_element_contents(_platform: EditorExportPlatform, _debug: bool) -> String:
	return """
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="com.oculus.intent.category.VR" />
            </intent-filter>
"""
