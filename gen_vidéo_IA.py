import pygame, sys, math
from pygame.locals import *
from Ball import Ball
from Wall import CircleWall, ArcWall
from pygame_screen_record import ScreenRecorder
import random
import time
import pandas as pd
import numpy as np
from color import generate_rgb_gradient, create_gradient_backward_surface

audio_path = r"C:\Users\ihadi\Downloads\pirate-tavern-full-version-167990.mp3"
ips = 60
W,H = 1080, 1920

try:
    # Initialiser Pygame and Pygame recorder
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    recorder = ScreenRecorder(ips)  # FPS souhaité
    recorder.start_rec()

    #Starting Parameters
    nb_cercles = 15
    radius_step = 30
    starting_radius = 50
    center = (540, 960)
    start_angle = 0
    end_angle = math.pi * 1.8
    bool_trail = True

    #Creating Objects
    colors = generate_rgb_gradient((255, 0, 0), (255, 255, 255), nb_cercles)
    color_index = 0
    ball = Ball(center[0], 
                center[1], 
                radius=5, 
                color=(255,255,255), 
                restitution=1, 
                x_speed=3, 
                y_speed=4, 
                mass=0.1,
                trail_length=20,
                bool_trail=bool_trail)
    walls = []
    start_point = random.uniform(math.pi,math.pi*2)

    for i in range(nb_cercles):
        walls.append(ArcWall(center[0], 
                             center[1], 
                             radius=starting_radius+(i + 1) * radius_step, 
                             id=i, 
                             start_angle=start_angle+start_point, 
                             end_angle=end_angle+start_point, 
                             color=colors[i]))
        
    walls = sorted(walls, key=lambda w: w.area_of_wall())
    onset_index = 0
    rot = [0.006*math.log(num+4) for num, i in enumerate(walls)]
    
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
        
        # Change background color based on time
        #screen.fill(colors[color_index])
        screen.fill((15, 15, 20))
        #screen.blit(create_gradient_backward_surface(W, H, (0, 0, 0), (0, 0, 0)), (0, 0))

        # Collision on each arcs
        for num, wall in enumerate(walls):
            wall.draw(screen)
            if num == 0:
                destroy = ball.check_collision_and_gravity_on_circles(wall)
                if destroy:
                    walls.remove(wall)

        # Walls rotation
        for num, wall in enumerate(walls):
            wall.start_angle += rot[wall.id]
            wall.end_angle += rot[wall.id]

        #Moving and drawing the ball
        ball.move()
        ball.draw(screen) 
        
        # Update the display and maintain the frame rate
        pygame.display.flip()
        clock.tick(ips)
finally:
    # Stop the screen recorder
    recorder.stop_rec()
    recorder.save_recording(r"C:\Users\ihadi\Desktop\VideoResultTikTok\my_simulation.mp4")
    pygame.quit()        
