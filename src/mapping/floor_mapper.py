import numpy as np
import cv2 as cv
from data_structures.compound_pixel_grid import CompoundExpandablePixelGrid
from data_structures.angle import Angle
import imutils

class FloorMapper:
    def __init__(self, pixel_grid: CompoundExpandablePixelGrid, tile_resolution, tile_size, camera_distance_from_center) -> None:
        self.pixel_grid = pixel_grid
        self.tile_resolution = tile_resolution
        self.tile_size = tile_size
        self.pixel_per_m = tile_resolution / tile_size
        self.pov_distance_from_center = round((camera_distance_from_center + 0.03) * self.pixel_per_m) 

        tiles_up = 1
        tiles_down = 1
        tiles_sides = 1

        min_x = self.tile_resolution * tiles_sides
        max_x = self.tile_resolution * (tiles_sides + 1)
        min_y = self.tile_resolution * tiles_up
        max_y = self.tile_resolution * (tiles_up + 1)

        self.center_tile_points_in_final_image = np.array(((min_x, min_y),
                                                           (max_x, min_y),
                                                           (max_x, max_y),
                                                           (min_x, max_y),), dtype=np.float32)
        
        self.center_tile_points_in_input_image = np.array(([0, 24],  [39, 24], [32, 16], [7, 16]), dtype=np.float32)

        self.flattened_image_shape = (self.tile_resolution * (tiles_sides * 2 + 1),
                                      self.tile_resolution * (tiles_up + tiles_down + 1))

    def flatten_camera_pov(self, camera_pov: np.ndarray):
        ipm_matrix = cv.getPerspectiveTransform(self.center_tile_points_in_input_image, 
                                                self.center_tile_points_in_final_image, 
                                                solveMethod=cv.DECOMP_SVD)
        
        ipm = cv.warpPerspective(camera_pov, ipm_matrix, self.flattened_image_shape, flags=cv.INTER_NEAREST)

        ipm = cv.resize(ipm, self.flattened_image_shape, interpolation=cv.INTER_CUBIC)

        blank_space = np.zeros((self.pov_distance_from_center, self.flattened_image_shape[0], 4), dtype=np.uint8)
        ipm = np.vstack((blank_space, ipm))

        return ipm
    
    def set_in_background(self, pov: np.ndarray, background=None):
        cv.imshow('pov', pov)
        max_dim = max(pov.shape)
        if background  is None: background = np.zeros((max_dim * 2, max_dim * 2, 4), dtype=np.uint8)

        start = (max_dim, max_dim - round(pov.shape[1] / 2))
        end =  (start[0] + pov.shape[0], start[1] + pov.shape[1])
        
        background[start[0]:end[0], start[1]:end[1], :] = pov[:,:,:]

        cv.imshow("pov in background", background)

        return background
    

    def get_global_camera_orientations(self, robot_orientation: Angle):
        global_camera_orientations = []
        for camera_orientation in self.pixel_grid.camera_orientations:
            o = camera_orientation + robot_orientation
            o.normalize()
            global_camera_orientations.append(o)
        
        return global_camera_orientations
    
    def rotate_image_to_angle(self, image: np.ndarray, angle: Angle):
        return imutils.rotate(image, angle.degrees, (image.shape[0] // 2, image.shape[1] // 2))
    
    def map_floor(self, camera_images, robot_grid_index):


        center_pov = self.flatten_camera_pov(np.rot90(camera_images[1].image,  k=3))
        center_pov = np.flip(center_pov, 1)
        center_pov = self.set_in_background(center_pov)
        center_pov = self.rotate_image_to_angle(center_pov, camera_images[1].orientation)

        right_pov = self.flatten_camera_pov(np.rot90(camera_images[0].image,  k=3))
        right_pov = np.flip(right_pov, 1)
        right_pov = self.set_in_background(right_pov)
        right_pov = self.rotate_image_to_angle(right_pov, camera_images[0].orientation )

        left_pov = self.flatten_camera_pov(np.rot90(camera_images[2].image, k=3))
        left_pov = np.flip(left_pov, 1)
        left_pov = self.set_in_background(left_pov)
        left_pov = self.rotate_image_to_angle(left_pov, camera_images[2].orientation)

        povs = center_pov + right_pov + left_pov

        cv.imshow("final_pov", povs[:, :, 3])

        self.load_povs_to_grid(robot_grid_index, povs)

    def load_povs_to_grid(self, robot_grid_index, povs):
        
        start = np.array((robot_grid_index[0] - (povs.shape[0] // 2), robot_grid_index[1] - (povs.shape[1] // 2)))
        end = np.array((robot_grid_index[0] + (povs.shape[0] // 2), robot_grid_index[1] + (povs.shape[1] // 2)))

        self.pixel_grid.expand_to_grid_index(start)
        self.pixel_grid.expand_to_grid_index(end)

        start = self.pixel_grid.grid_index_to_array_index(start)
        end = self.pixel_grid.grid_index_to_array_index(end)
        
        print("fc dtype", self.pixel_grid.arrays["floor_color"].dtype)


        self.pixel_grid.arrays["floor_color"][start[0]:end[0], start[1]:end[1]][povs[:,:,3] > 254] = povs[:,:,:3][povs[:,:,3] > 254]

        
        

