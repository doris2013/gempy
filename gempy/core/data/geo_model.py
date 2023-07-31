﻿import pprint
import warnings
from dataclasses import dataclass, field

import numpy as np

import gempy_engine.core.data.grid
from gempy_engine.core.data.legacy_solutions import LegacySolution
from gempy_engine.core.data import InterpolationOptions
from gempy_engine.core.data.input_data_descriptor import InputDataDescriptor
from gempy_engine.core.data.interpolation_input import InterpolationInput
from .structural_frame import StructuralFrame
from .transforms import Transform
from ..grid import Grid

"""
TODO:
    - [ ] StructuralFrame will all input points chunked on Elements. Here I will need a property to put all
    together to feed to InterpolationInput

"""


@dataclass
class GeoModelMeta:
    name: str
    creation_date: str
    last_modification_date: str
    owner: str


@dataclass(init=False)
class GeoModel:
    meta: GeoModelMeta
    structural_frame: StructuralFrame
    grid: Grid  # * This is the general gempy grid
    transform: Transform

    # region GemPy engine data types
    interpolation_options: InterpolationOptions  # * This has to be fed by USER

    # ? Are this more caching fields than actual fields?
    interpolation_grid: gempy_engine.core.data.grid.Grid = None
    _interpolationInput: InterpolationInput = None  # * This has to be fed by structural_frame
    _input_data_descriptor: InputDataDescriptor = None  # * This has to be fed by structural_frame

    # endregion

    _solutions: gempy_engine.core.data.solutions.Solutions = field(init=False, default=None)

    legacy_model: "gpl.Project" = None

    def __init__(self, name: str, structural_frame: StructuralFrame, grid: Grid,
                 interpolation_options: InterpolationOptions):
        # TODO: Fill the arguments properly
        self.meta = GeoModelMeta(
            name=name,
            creation_date=None,
            last_modification_date=None,
            owner=None
        )

        self.structural_frame = structural_frame  # ? This could be Optional

        self.grid = grid
        self.interpolation_options = interpolation_options
        self.transform = Transform.from_input_points(
            surface_points=self.surface_points,
            orientations=self.orientations
        )

    def __repr__(self):
        # TODO: Improve this
        return pprint.pformat(self.__dict__)

    @property
    def solutions(self):
        return self._solutions
    
    @solutions.setter
    def solutions(self, value):
        self._solutions = value
        for e, group in enumerate(self.structural_frame.structural_groups):
            group.solution = LegacySolution(  # ? Maybe I need to add more fields, but I am not sure yet
                scalar_field_matrix=self._solutions.raw_arrays.scalar_field_matrix[e],
                block_matrix=self._solutions.raw_arrays.block_matrix[e],
            )
        
        for e, element in enumerate(self.structural_frame.structural_elements[:-1]):  # * Ignore basement
            
            dc_mesh = self._solutions.dc_meshes[e] if self._solutions.dc_meshes is not None else None
            # TODO: This meshes are in the order of the scalar field
            element.vertices = (self.transform.apply_inverse(dc_mesh.vertices) if dc_mesh is not None else None)
            element.edges = (dc_mesh.edges if dc_mesh is not None else None)
            
        
    @property
    def surface_points(self):
        return self.structural_frame.surface_points

    @property
    def orientations(self):
        return self.structural_frame.orientations

    @property
    def interpolation_input(self):
        if self.structural_frame.is_dirty:
            n_octree_lvl = self.interpolation_options.number_octree_levels
            compute_octrees: bool = n_octree_lvl > 1
            
            # * Set regular grid to the octree resolution. ? Probably a better way to do this would be to make regular_grid resolution a property
            if compute_octrees:
                if self.grid.regular_grid.resolution is not None:
                    warnings.warn(
                        message="You are using octrees and passing a regular grid. The resolution of the regular grid will be overwritten",
                        category=UserWarning
                    )
                self.grid.regular_grid.set_regular_grid(
                    extent=self.grid.regular_grid.extent,
                    resolution=np.array([2 ** n_octree_lvl] * 3)
                )
                
            self._interpolationInput = InterpolationInput.from_structural_frame(
                structural_frame=self.structural_frame,
                grid=self.grid,
                transform=self.transform,
                octrees=compute_octrees
            )
            
        return self._interpolationInput

        
    @property
    def input_data_descriptor(self) -> InputDataDescriptor:
        # TODO: This should have the exact same dirty logic as interpolation_input
        return self.structural_frame.input_data_descriptor
