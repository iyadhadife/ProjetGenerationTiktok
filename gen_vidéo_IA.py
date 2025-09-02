import pygame, sys, math
from pygame.locals import *
from Ball import Ball
from Wall import CircleWall, ArcWall
from pygame_screen_record import ScreenRecorder
import random

ips = 60
try:
    # Initialiser Pygame
    pygame.init()
    screen = pygame.display.set_mode((600, 600))
    clock = pygame.time.Clock()
    recorder = ScreenRecorder(ips)  # FPS souhaité
    recorder.start_rec()

    # Lecture audio
    audio_path = r"C:\Users\ihadi\Downloads\pirate-tavern-full-version-167990.mp3"
    pygame.mixer.music.load(audio_path)
    pygame.mixer.music.play()

    nb_cercles = 3
    rayon_step = 50
    center = (300, 300)
    start_angle = 0            
    end_angle = math.pi * 1.8
    ball = Ball(center[0], center[1], radius=5, color=(255, 0, 0), restitution=0.8, x_speed=2, y_speed=3, mass=0.1)
    walls = [ArcWall(center[0], center[1], radius=(i + 1) * rayon_step, id=i, start_angle=math.pi*random.uniform(0,0.5), end_angle=math.pi*random.uniform(1.5,2)) for i in range(nb_cercles)]
    walls = sorted(walls, key=lambda w: w.area_of_wall())

    while True:
        for e in pygame.event.get():
            if e.type == QUIT:
                pygame.quit()
                sys.exit()

        screen.fill((0, 0, 0))
        deplacement = False
        # Collision avec chaque cercle
        for num, wall in enumerate(walls):
            if num == 0:
                destroy = ball.check_collision_and_gravity_on_circles(wall)
                if destroy:
                    walls.remove(wall)
            wall.draw(screen)

        #Rotation des murs
        for wall in walls:
            wall.start_angle += 0.01
            wall.end_angle += 0.01

        ball.move()
        ball.draw(screen)

        pygame.display.flip()
        clock.tick(ips)
finally:
    recorder.stop_rec()
    recorder.save_recording(r"C:\Users\ihadi\Desktop\VideoResultTikTok\my_simulation.mp4")
    pygame.quit()        
