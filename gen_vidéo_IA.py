import pygame, sys, math
from pygame.locals import *
from Ball import Ball
from Wall import CircleWall, ArcWall
from pygame_screen_record import ScreenRecorder
import random
from music_highlight import onsets_frames, velocity_ball
import time

audio_path = r"C:\Users\ihadi\Downloads\pirate-tavern-full-version-167990.mp3"
highlights = onsets_frames(audio_path=audio_path)
ips = 60

try:
    # Initialiser Pygame and Pygame recorder
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    screen = pygame.display.set_mode((600, 600))
    clock = pygame.time.Clock()
    recorder = ScreenRecorder(ips)  # FPS souhaité
    recorder.start_rec()

    #Starting Parameters
    nb_cercles = 30
    rayon_step = 20
    center = (300, 300)
    start_angle = 0            
    end_angle = math.pi * 1.8

    #Creating Objects
    ball = Ball(center[0], center[1], radius=5, color=(255, 0, 0), restitution=0.8, x_speed=2, y_speed=3, mass=0.1)
    walls = []
    start_point = random.uniform(math.pi,math.pi*2)
    for i in range(nb_cercles):
        walls.append(CircleWall(center[0], center[1], radius=(i + 1) * rayon_step, id=i, start_angle=start_angle+start_point, end_angle=end_angle+start_point))
    walls = sorted(walls, key=lambda w: w.area_of_wall())
    onset_index = 0

    # Audio
    pygame.mixer.music.load(audio_path)
    pygame.mixer.music.play()
    start_time = time.time()
    # Main loop
    while True:
        for e in pygame.event.get():
            if e.type == QUIT:
                pygame.quit()
                sys.exit()
        
        screen.fill((0, 0, 0))
        deplacement = False

        if len(highlights)>0:
            highlights = velocity_ball(highlights, time.time(), ball, walls[0])

        # Collision on each arcs
        for num, wall in enumerate(walls):
            wall.draw(screen)
            if num == 0:
                destroy = ball.check_collision_and_gravity_on_circles(wall)
                if destroy:
                    walls.remove(wall)

        # Walls rotation
        for wall in walls:
            wall.start_angle += 0.01
            wall.end_angle += 0.01

        #Moving and drawing the ball
        ball.move()
        ball.draw(screen)

        pygame.display.flip()
        clock.tick(ips)
finally:
    # Stop the screen recorder
    recorder.stop_rec()
    recorder.save_recording(r"C:\Users\ihadi\Desktop\VideoResultTikTok\my_simulation.mp4")
    pygame.quit()        
