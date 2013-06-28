# Gel

This is an extremely simple interface to the OpenGL engine. It relys on knowledge of OpenGL to use, and makes getting started faster by doing the proper setup and providing the proper hooks.

## class Gel

The main class `Gel` should be inherited in the class containing the top level logic for the program. The following hooks are called to render the graphics.

### setup

Code to be executed before the OpenGL loop starts. This is where any initialization should happen. It is recommended that any variables needed in other hooks be saved in instance variables.

### draw

The code to be called when OpenGL asks for a new image of the scene. `Gel::Objects` should be favored over hand writing the vertexes in this function.

### loop

Called when OpenGL is idle.

TODO:L Make a game loop, with a notion of frame-rate.

### keyboard

Hook to handle the keyboard event, including all ASCII symbols.

### special_keyboard

Hook to handle the non ASCII keyboard symbols.
