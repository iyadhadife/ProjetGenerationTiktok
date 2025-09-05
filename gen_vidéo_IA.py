import pygame, sys, math
from pygame.locals import *
from Ball import Ball
from Wall import CircleWall, ArcWall
from pygame_screen_record import ScreenRecorder
import threading
import random
import time
import pandas as pd
import numpy as np
from color import generate_rgb_gradient, create_gradient_backward_surface
from merging_audio_video import charger_video, record_audio

#video and audio paths
audio_path = r"C:\Users\ihadi\Downloads\pirate-tavern-full-version-167990.mp3"
video_temp = r"C:\Users\ihadi\Desktop\VideoResultTikTok\corbeille\my_simulation.mp4"
audio_temp = r"C:\Users\ihadi\Desktop\VideoResultTikTok\corbeille\my_simulation_wav.wav"
# Chemin vers ton fichier son
ball_bouncing_sound_path = r"C:\Users\ihadi\Desktop\ProjetGenerationTiktok\bin\bouncing_sound\bouncing_ball_v1.mp3"

#video parameters
ips = 60
W,H = 1080, 1920

try:
    # Initialiser Pygame and Pygame recorder
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    recorder = ScreenRecorder(ips)  
    recorder.start_rec()
    stop_event = threading.Event()
    audio_thread = threading.Thread(target=record_audio, args=(stop_event, audio_temp))
    audio_thread.start()


    #Starting Parameters
    nb_cercles = 15
    radius_step = 25
    starting_radius = 50
    center = (540, 960)
    start_angle = 0
    end_angle = math.pi * 1.8
    bool_trail = True
    max_speed = 15
    
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
    rot = [0.01*math.log(num+2) for num, i in enumerate(walls)]
    
    # Audio
    pygame.mixer.music.load(audio_path)
    ball_bouncing_sound = pygame.mixer.Sound(ball_bouncing_sound_path)
    pygame.mixer.music.play()
    start_time = time.time()

    # Main loop
    while True:
        for e in pygame.event.get():
            if e.type == QUIT:
                pygame.quit()
                sys.exit()
        
        # Change background color based on time
        screen.fill((15, 15, 20))
        #screen.fill(colors[color_index])
        #screen.blit(create_gradient_backward_surface(W, H, (0, 0, 0), (0, 0, 0)), (0, 0))

        # Collision on each arcs
        for num, wall in enumerate(walls):
            wall.draw(screen)
            if num == 0:
                destroy = ball.check_collision_and_gravity_on_circles(wall,ball_bouncing_sound=ball_bouncing_sound)
                if destroy:
                    walls.remove(wall)

        # Walls rotation
        for num, wall in enumerate(walls):
            wall.start_angle += rot[num]
            wall.end_angle += rot[num]

        #Moving and drawing the ball
        ball.move(max_speed=max_speed)
        ball.draw(screen)

        # Update the display and maintain the frame rate
        pygame.display.flip()
        clock.tick(ips)
finally:
    # Stop the screen recorder
    recorder.stop_rec()
    recorder.save_recording(video_temp)

    # Stop audio
    stop_event.set()
    audio_thread.join()

    # Fusion audio + vidéo
    print("🎬 Fusion audio + vidéo...")
    charger_video(audio_temp, video_temp)

    pygame.quit()        
