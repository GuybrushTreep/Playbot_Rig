# Playbot blender rig  
<img title="Script" src="images/Rig_Anim.gif" width="400">

## How to use
### move and rotate the robot
<img title="Script" src="images/Rig_Move-Rotate.gif" width="400">

The robot's body movement drives the wheel calculations.
**Important:** The robot cannot move forward/backward and turn at the same time. Each movement must be separated into distinct actions:

First complete the turn, then move forward/backward Or first complete the forward/backward movement, then turn.
Combining these movements in the same frame will result in incorrect wheel calculations

### rotate the head 

<img title="Script" src="images/Rig_Head_Rotate.gif" width="400">

Head rotation directly controls the servo position. Rotation constraints prevent exceeding physical rotation limits.

### Expression controller 
<img title="Script" src="images/Rig_Expressions_Controls.gif" width="400">

In **pose mode**, you can cycle through various expression images for eyes and eyebrows, along with blink and mouth controls.

#### Expressions library 
<img title="Script" src="images/Rig_Library.gif" width="400">

To help speed up your animation process, you can also access a library of pre-built expressions.

### Bones controller

<img title="Script" src="images/Rig_Bones_Controls.gif" width="400">

You can also fine tune transformations for each facial bones.