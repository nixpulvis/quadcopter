require 'opengl'
require 'gel/version'

class Gel
  include Gl, Glu, Glut

  def initialize(title, width, height)
    glutInit
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(width, height)
    glutInitWindowPosition(100, 100)
    glutCreateWindow(title)

    # Basic setup
    glClearDepth(1)
    glEnable(GL_DEPTH_TEST)

    setup if defined? setup

    glutIdleFunc(-> do
      loop

      glutPostRedisplay
    end) if defined? loop

    glutDisplayFunc(-> do
      glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
      glLoadIdentity

      draw

      glFlush
      glutSwapBuffers
    end) if defined? draw

    glutKeyboardFunc(-> (key, x, y) do
      keyboard(key, x, y)

      glutPostRedisplay
    end) if defined? keyboard

    glutSpecialFunc(-> (key, x, y) do
      special_keyboard(key, x, y)

      glutPostRedisplay
    end) if defined? special_keyboard

    glutMainLoop
  end

  private

  def drawBox(width, height, depth)
    # Front surface.
    glBegin(GL_QUADS)
    glNormal3d(0, 0, 1)
    glColor3f(1.0, 1.0, 1.0)
    glVertex3f( width, -height, -depth)  # P1 is red
    glVertex3f( width,  height, -depth)  # P2 is green
    glVertex3f(-width,  height, -depth)  # P3 is blue
    glVertex3f(-width, -height, -depth)  # P4 is purple
    glEnd

    # Back surface.
    glBegin(GL_QUADS)
    glNormal3d(0, 0, -1)
    glColor3f(0.5, 0.5, 0.5)
    glVertex3f( width, -height, depth)
    glVertex3f( width,  height, depth)
    glVertex3f(-width,  height, depth)
    glVertex3f(-width, -height, depth)
    glEnd

    # Right surface.
    glBegin(GL_QUADS)
    glNormal3d(1, 0, 0)
    glColor3f(1.0, 0.0, 0.0)
    glVertex3f(width, -height, -depth)
    glVertex3f(width,  height, -depth)
    glVertex3f(width,  height,  depth)
    glVertex3f(width, -height,  depth)
    glEnd

    # Left surface.
    glBegin(GL_QUADS)
    glNormal3d(-1, 0, 0)
    glColor3f(1.0, 0.0, 0.0)
    glVertex3f(-width, -height,  depth)
    glVertex3f(-width,  height,  depth)
    glVertex3f(-width,  height, -depth)
    glVertex3f(-width, -height, -depth)
    glEnd

    # Top surface.
    glBegin(GL_QUADS)
    glNormal3d(0, 1, 0)
    glColor3f(0.0, 1.0, 0.0)
    glVertex3f( width,  height,  depth)
    glVertex3f( width,  height, -depth)
    glVertex3f(-width,  height, -depth)
    glVertex3f(-width,  height,  depth)
    glEnd

    # Bottom surface.
    glBegin(GL_QUADS)
    glNormal3d(0, -1, 0)
    glColor3f(0.0, 0.0, 1.0)
    glVertex3f( width, -height, -depth)
    glVertex3f( width, -height,  depth)
    glVertex3f(-width, -height,  depth)
    glVertex3f(-width, -height, -depth)
    glEnd
  end
end
