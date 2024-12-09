
bl_info = {
    "name": "Playbot Exporter",
    "author": "Guillaume Loquin",
    "version": (1, 0),
    "blender": (4, 2, 3),
    "location": "Properties > Output > Robot Animation Export",
    "description": "Export Playbot robot animations to a firmware-compatible format",
    "warning": "",
    "doc_url": "",
    "category": "Import-Export",
}

import bpy
import math
import os
from mathutils import Vector, Matrix
from bpy.props import StringProperty, FloatProperty, IntProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper

def radians_to_ticks(angle_rad, ticks_per_revolution=870):
    """
    Convert an angle in radians to encoder ticks
    
    Args:
        angle_rad (float): Angle in radians
        ticks_per_revolution (int): Number of encoder ticks per wheel revolution
        
    Returns:
        int: Number of ticks
    """
    ticks = (angle_rad / (2 * math.pi)) * ticks_per_revolution
    return round(ticks)

def ticks_to_radians(ticks, ticks_per_revolution=870):
    """
    Convert encoder ticks to angle in radians
    
    Args:
        ticks (int): Number of encoder ticks
        ticks_per_revolution (int): Number of encoder ticks per wheel revolution
        
    Returns:
        float: Angle in radians
    """
    return (ticks * 2 * math.pi) / ticks_per_revolution

def rotation_to_microseconds(angle_rad):
    """
    Convert an angle in radians to servo microseconds
    0 radians = 1500 µs (center position)
    pi radians (180°) = 2000 µs (max right)
    -pi radians (-180°) = 1000 µs (max left)
    
    Args:
        angle_rad (float): Angle in radians
        
    Returns:
        float: Servo position in microseconds (1000-2000)
    """
    angle_deg = math.degrees(angle_rad)
    microseconds = 1500 + (angle_deg * (500 / 90))
    return min(max(microseconds, 1000), 2000)

def calculate_rotations(body, head, l_wheel, r_wheel, wheel_diameter_mm, wheel_spacing_mm, ticks_per_rev):
    scene = bpy.context.scene
    prev_pos = None
    prev_rot = None
    
    wheel_radius = wheel_diameter_mm / 2
    wheel_spacing = wheel_spacing_mm
    
    total_left_ticks = 0
    total_right_ticks = 0
    frame_data = []
    
    # Initial setup
    scene.frame_set(scene.frame_start)
    start_pos = body.matrix_world.translation.copy()
    start_rot = body.rotation_euler.z
    
    servo_us = rotation_to_microseconds(head.rotation_euler.y)
    frame_data.append((scene.frame_start, servo_us, 0, 0))
    prev_pos = start_pos
    prev_rot = body.rotation_euler.z
    
    for frame in range(scene.frame_start + 1, scene.frame_end + 1):
        scene.frame_set(frame)
        current_pos = body.matrix_world.translation.copy()
        current_rot = body.rotation_euler.z
        
        servo_us = rotation_to_microseconds(head.rotation_euler.y)
        
        # Check if robot is turning
        rot_diff = current_rot - prev_rot
        if abs(rot_diff) > 0.01:
            arc_length = (wheel_spacing * abs(rot_diff)) / 2
            wheel_angle = arc_length / wheel_radius
            turn_ticks = radians_to_ticks(wheel_angle, ticks_per_rev)
            
            if rot_diff > 0:  # Rotation horaire (droite)
                right_ticks = turn_ticks      # Roue droite vers l'avant
                left_ticks = -turn_ticks      # Roue gauche vers l'arrière
            else:  # Rotation anti-horaire (gauche)
                right_ticks = -turn_ticks     # Roue droite vers l'arrière
                left_ticks = turn_ticks       # Roue gauche vers l'avant
                
        else:
            # Calculate linear movement
            movement = current_pos - prev_pos
            distance = movement.length
            
            # Calculate movement relative to initial direction
            movement_y = movement.y
            
            # Convert distance to wheel rotation angle
            wheel_angle = distance / wheel_radius
            ticks = radians_to_ticks(wheel_angle, ticks_per_rev)
            
            # Si movement_y est négatif, le robot avance (car orienté vers -Y)
            # Si movement_y est positif, le robot recule
            if movement_y < 0:
                left_ticks = right_ticks = ticks
            else:
                left_ticks = right_ticks = -ticks
        
        total_left_ticks += left_ticks
        total_right_ticks += right_ticks
        
        frame_data.append((frame, servo_us, total_right_ticks, total_left_ticks))
        
        prev_pos = current_pos
        prev_rot = current_rot
    
    return frame_data
class ROBOT_OT_export_rotations(bpy.types.Operator, ExportHelper):
    """Export robot animation to a format compatible with the robot's firmware"""
    bl_idname = "robot.export_rotations"
    bl_label = "Export Animation"
    filename_ext = ".txt"
    
    filter_glob: StringProperty(
        default="*.txt",
        options={'HIDDEN'},
        maxlen=255,
    )
    
    render_frames: BoolProperty(
        name="Render Frames",
        description="Export rendered frames along with animation data",
        default=False
    )
    
    def invoke(self, context, event):
        self.render_frames = context.scene.robot_props.render_frames
        return ExportHelper.invoke(self, context, event)
    
    def render_viewport(self, context, filepath):
        """Helper function to render viewport to file"""
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                # Find the 3D VIEW region
                region = None
                for r in area.regions:
                    if r.type == 'WINDOW':
                        region = r
                        break
                
                if region:
                    # Set viewport to camera view
                    space = area.spaces[0]
                    if space.type == 'VIEW_3D':
                        # Store current view
                        old_perspective = space.region_3d.view_perspective
                        # Switch to camera view
                        space.region_3d.view_perspective = 'CAMERA'
                        
                        # Do the render
                        override = context.copy()
                        override['area'] = area
                        override['region'] = region
                        with context.temp_override(**override):
                            bpy.ops.render.opengl(write_still=True)
                        
                        # Restore previous view
                        space.region_3d.view_perspective = old_perspective
                    return True
        return False
    
    def execute(self, context):
        props = context.scene.robot_props
        try:
            body = bpy.data.objects[props.body_name]
            head = bpy.data.objects[props.head_name]
            l_wheel = bpy.data.objects[props.left_wheel_name]
            r_wheel = bpy.data.objects[props.right_wheel_name]
        except KeyError:
            self.report({'ERROR'}, "Objects not found. Check names.")
            return {'CANCELLED'}
        
        frame_data = calculate_rotations(
            body, head, l_wheel, r_wheel,
            props.wheel_diameter_mm,
            props.wheel_spacing_mm,
            props.ticks_per_rev
        )
        
        # Automatically bake wheel animations using existing operator
        bpy.ops.robot.bake_wheel_rotation('EXEC_DEFAULT')
        
        # Save current render settings if rendering frames
        if self.render_frames:
            original_path = context.scene.render.filepath
            
            # Store viewport shading settings for each 3D viewport
            viewport_settings = []
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            viewport_settings.append({
                                'space': space,
                                'shading': space.shading.type,
                                'overlay': space.overlay.show_overlays
                            })
                            # Ensure viewport is in rendered mode
                            space.shading.type = 'RENDERED'
                            space.overlay.show_overlays = False
            
            # Configure render output
            render_dir = os.path.splitext(self.filepath)[0] + "_frames"
            os.makedirs(render_dir, exist_ok=True)
        
        # Export animation data
        with open(self.filepath, 'w') as f:
            for frame, servo, right_ticks, left_ticks in frame_data:
                f.write(f"{frame}/{servo:.0f}/{right_ticks}/{left_ticks}\n")
                
                # Render frame if enabled
                if self.render_frames:
                    # Set the frame
                    context.scene.frame_set(frame)
                    
                    # Set output path for this frame
                    frame_path = os.path.join(render_dir, f"frame_{frame:04d}.png")
                    context.scene.render.filepath = frame_path
                    
                    # Render current frame
                    if not self.render_viewport(context, frame_path):
                        self.report({'WARNING'}, f"Could not render frame {frame}")
        
        # Restore render settings and viewport states
        if self.render_frames:
            # Restore viewport settings
            for settings in viewport_settings:
                settings['space'].shading.type = settings['shading']
                settings['space'].overlay.show_overlays = settings['overlay']
            
            context.scene.render.filepath = original_path
            
            self.report({'INFO'}, f"Animation and frames exported to {render_dir}")
        else:
            self.report({'INFO'}, f"Animation exported to {self.filepath}")
            
        return {'FINISHED'}
    
class ROBOT_OT_bake_wheel_rotation(bpy.types.Operator):
    """Bake calculated wheel rotations into the timeline"""
    bl_idname = "robot.bake_wheel_rotation"
    bl_label = "Bake Wheel Animation"
    bl_description = "Bake the calculated wheel rotations into the timeline"
    
    @classmethod
    def poll(cls, context):
        return context.scene.robot_props.left_wheel_name in bpy.data.objects and \
               context.scene.robot_props.right_wheel_name in bpy.data.objects
    
    def execute(self, context):
        props = context.scene.robot_props
        try:
            body = bpy.data.objects[props.body_name]
            head = bpy.data.objects[props.head_name]
            l_wheel = bpy.data.objects[props.left_wheel_name]
            r_wheel = bpy.data.objects[props.right_wheel_name]
        except KeyError:
            self.report({'ERROR'}, "Objects not found. Check names.")
            return {'CANCELLED'}
        
        frame_data = calculate_rotations(
            body, head, l_wheel, r_wheel,
            props.wheel_diameter_mm,
            props.wheel_spacing_mm,
            props.ticks_per_rev
        )
        
        # Store current selection state
        original_active = context.view_layer.objects.active
        original_selected = {obj: obj.select_get() for obj in bpy.data.objects}
        
        # Clear selection using object properties
        for obj in bpy.data.objects:
            obj.select_set(False)
        
        # Process each wheel
        for wheel, is_left in [(l_wheel, True), (r_wheel, False)]:
            wheel.select_set(True)
            context.view_layer.objects.active = wheel
            
            # Create or get animation data
            if not wheel.animation_data:
                wheel.animation_data_create()
            
            if not wheel.animation_data.action:
                wheel.animation_data.action = bpy.data.actions.new(name=f"{wheel.name}Action")
            
            # Remove existing rotation curve if any
            if wheel.animation_data.action:
                fc = wheel.animation_data.action.fcurves.find('rotation_euler', index=1)
                if fc:
                    wheel.animation_data.action.fcurves.remove(fc)
            
            # Insert keyframes for each frame
            for frame, servo, right_ticks, left_ticks in frame_data:
                ticks = left_ticks if is_left else right_ticks
                angle = ticks_to_radians(ticks, props.ticks_per_rev)
                
                wheel.rotation_euler.y = angle
                wheel.keyframe_insert(data_path="rotation_euler", frame=frame, index=1)
            
            wheel.select_set(False)
        
        # Restore original selection state
        for obj, was_selected in original_selected.items():
            obj.select_set(was_selected)
        context.view_layer.objects.active = original_active
        
        self.report({'INFO'}, "Wheel animations baked successfully")
        return {'FINISHED'}

class RobotProperties(bpy.types.PropertyGroup):
    """Properties for the robot animation exporter"""
    body_name: StringProperty(
        name="Body",
        description="Name of the robot's body object",
        default="body"
    )
    
    head_name: StringProperty(
        name="Head",
        description="Name of the robot's head (servo) object",
        default="head"
    )
    
    left_wheel_name: StringProperty(
        name="Left Wheel",
        description="Name of the left wheel object",
        default="L_Wheel"
    )
    
    right_wheel_name: StringProperty(
        name="Right Wheel",
        description="Name of the right wheel object",
        default="R_Wheel"
    )
    
    wheel_diameter_mm: FloatProperty(
        name="Wheel Diameter (mm)",
        description="Wheel diameter in millimeters",
        default=33.50,
        min=1.0
    )
    
    wheel_spacing_mm: FloatProperty(
        name="Wheel Spacing (mm)",
        description="Distance between wheel centers in millimeters",
        default=81.0,
        min=1.0
    )
    
    ticks_per_rev: IntProperty(
        name="Ticks per Revolution",
        description="Number of encoder ticks per wheel revolution",
        default=813,
        min=1
    )
    
    render_frames: BoolProperty(
        name="Render Frames",
        description="Export rendered frames along with animation data",
        default=False
    )

class ROBOT_PT_panel(bpy.types.Panel):
    """Panel for robot animation export settings"""
    bl_label = "Robot Animation Export"
    bl_idname = "ROBOT_PT_panel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "output"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.robot_props
        
        box = layout.box()
        box.label(text="Object Names:")
        box.prop(props, "body_name")
        box.prop(props, "head_name")
        box.prop(props, "left_wheel_name")
        box.prop(props, "right_wheel_name")
        
        box = layout.box()
        box.label(text="Robot Parameters:")
        box.prop(props, "wheel_diameter_mm")
        box.prop(props, "wheel_spacing_mm")
        box.prop(props, "ticks_per_rev")
        
        box = layout.box()
        box.label(text="Export Options:")
        box.prop(props, "render_frames")
        
        layout.operator("robot.export_rotations")
        layout.operator("robot.bake_wheel_rotation")

# List of all classes to register
classes = (
    RobotProperties,
    ROBOT_OT_export_rotations,
    ROBOT_OT_bake_wheel_rotation,
    ROBOT_PT_panel,
)

def register():
    """Register all classes and properties when the addon is enabled"""
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.robot_props = bpy.props.PointerProperty(type=RobotProperties)

def unregister():
    """Unregister all classes and clean up properties when the addon is disabled"""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.robot_props

if __name__ == "__main__":
    register()