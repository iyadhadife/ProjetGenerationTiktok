import pygame
import math
from Ball import Ball

class Wall:
    """Classe générique pour un mur ou une frontière."""
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def distance_to_middle(self,  ball : Ball):
        """Calculer la distance à la balle (à surcharger si nécessaire)."""
        raise NotImplementedError("Cette méthode doit être surchargée dans la sous-classe.")

    def in_the_wall(self, ball : Ball):
        """Vérifier si la balle est à l'intérieur du mur (à surcharger)."""
        raise NotImplementedError("Cette méthode doit être surchargée dans la sous-classe.")

    def area_of_wall(self):
        """Retourne l'aire (à surcharger)."""
        raise NotImplementedError("Cette méthode doit être surchargée dans la sous-classe.")

    def Correct_ball_position(self, ball : Ball):
        """Retourne l'aire (à surcharger)."""
        raise NotImplementedError("Cette méthode doit être surchargée dans la sous-classe.")

class CircleWall(Wall):
    def __init__(self, x, y, radius, id):
        self.x = x
        self.y = y
        self.radius = radius
        self.id = id

    def draw(self, surface):
        pygame.draw.circle(surface, (0, 100, 255), (self.x, self.y), self.radius, 1)

    def distance_to_middle(self, ball : Ball):
        dx = ball.x - self.x
        dy = ball.y - self.y
        dist = math.hypot(dx, dy)
        return dist, dx, dy

    def in_the_wall(self, ball : Ball):
        dist, dx, dy = self.distance_to_middle(ball)
        return dist + ball.r < self.radius
    
    def Correct_ball_position(self, ball : Ball):
        dist, dx, dy = self.distance_to_middle(ball)
        ball.x = self.x + (dx / dist) * (self.radius - ball.r)
        ball.y = self.y + (dy / dist) * (self.radius - ball.r)

    def area_of_wall(self):
        return math.pi * (self.radius ** 2)
