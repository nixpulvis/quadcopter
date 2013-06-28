require 'opengl'
require 'gel/version'
require 'gel/objects'

class Gel
  include Gl, Glu, Glut

  def initialize(title, width, height)
    glutInit  # TODO: what is this, should I be hooking into it?
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)  # TODO: What config makes sense here.
    glutInitWindowSize(width, height)
    glutInitWindowPosition(100, 100)  # TODO: Add config for this.
    glutCreateWindow(title)

    # Setup the OpenGL run.
    _setup

    # Run user setup
    setup if defined? setup

    # Define the idle function if it exists.
    glutIdleFunc(-> do
      loop

      glutPostRedisplay
    end) if defined? loop

    # Define the draw function if it exists. Drawing code should
    # handle making objects, this code will take care of loading a clean
    # working state, and pushing changes to the screen.
    glutDisplayFunc(-> do
      glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
      glLoadIdentity

      draw

      glFlush
      glutSwapBuffers
    end) if defined? draw

    glutMouseFunc(-> (button, state, x, y) do
      mouse_click(button, state, x, y)
    end) if defined? mouse_click

    glutPassiveMotionFunc(-> (x, y) do
      mouse_move(x, y)
    end) if defined? mouse_move

    # Define the keyboard handler if it exists.
    glutKeyboardFunc(-> (key, x, y) do
      keyboard(key, x, y)

      glutPostRedisplay
    end) if defined? keyboard

    # Define the special keyboard handler if it exists.
    # Special keys are those not included in UTF like up arrow.
    glutSpecialFunc(-> (key, x, y) do
      special_keyboard(key, x, y)

      glutPostRedisplay
    end) if defined? special_keyboard

    # Kick off our OpenGl Run.
    glutMainLoop
  end

  private

  def _setup
    glClearDepth(1)
    glEnable(GL_DEPTH_TEST)
  end

end
