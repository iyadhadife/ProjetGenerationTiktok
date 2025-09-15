import pygame
from Wall import Wall

def animate_wall(nb_frames, radius_step, walls, walls_to_remove : Wall):
    walls.remove(walls_to_remove)
    annimations = []
    for wall in walls:
        wall.radius -= (radius_step/nb_frames)* nb_frames
    annimations.append(walls.copy())
    return annimations