# Purpose: Design a bi-uniform constrained polygonal field using the common
# design interface with a single U-tube, multiple U-tube and coaxial tube
# borehole heat exchanger.

# This search is described in section 4.4.5 from pages 146-148 in Cook (2021).

from ghedesigner.manager import GHEManager
from ghedesigner.tests.ghe_base_case import GHEBaseTest

prop_boundary = [
    [19.46202532, 108.8860759],
    [19.67827004, 94.46835443],
    [24.65189873, 75.3164557],
    [37.19409283, 56.59493671],
    [51.68248945, 45.83544304],
    [84.33544304, 38.94936709],
    [112.0147679, 38.94936709],
    [131.0443038, 35.50632911],
    [147.2626582, 28.83544304],
    [160.8860759, 18.07594937],
    [171.6983122, 18.29113924],
    [167.157173, 72.94936709],
    [169.1033755, 80.48101266],
    [177.3206751, 99.63291139],
    [182.2943038, 115.7721519],
    [182.2943038, 121.3670886],
    [155.0474684, 118.5696203],
    [53.19620253, 112.3291139]
]

no_go_zones = [[
    [74.38818565, 80.69620253],
    [73.0907173, 53.36708861],
    [93.85021097, 52.50632911],
    [120.0158228, 53.15189873],
    [121.5295359, 62.18987342],
    [128.8818565, 63.26582278],
    [128.8818565, 78.5443038],
    [129.0981013, 80.91139241],
    [108.5548523, 81.34177215],
    [104.0137131, 110],
    [95.58016878, 110],
    [95.7964135, 81.7721519]
]]


class TestFindBiRectangleConstrainedDesign(GHEBaseTest):

    def test_single_u_tube(self):
        ghe = GHEManager()
        ghe.set_single_u_tube_pipe(
            inner_diameter=0.0216, outer_diameter=0.02667, shank_spacing=0.0323,
            roughness=1.0e-6, conductivity=0.4, rho_cp=1542000.0)
        ghe.set_soil(conductivity=2.0, rho_cp=2343493.0, undisturbed_temp=18.3)
        ghe.set_grout(conductivity=1.0, rho_cp=3901000.0)
        ghe.set_fluid()
        ghe.set_borehole(height=96.0, buried_depth=2.0, diameter=0.150)
        ghe.set_simulation_parameters(num_months=240, max_eft=35, min_eft=5, max_height=135, min_height=60)
        ghe.set_ground_loads_from_hourly_list(self.get_atlanta_loads())
        ghe.set_geometry_constraints_bi_rectangle_constrained(
            b_min=5.0, b_max_x=25.0, b_max_y=25.0,
            property_boundary=prop_boundary, no_go_boundaries=no_go_zones)
        ghe.set_design(flow_rate=0.2, flow_type_str="borehole")
        ghe.find_design()
        output_file_directory = self.test_outputs_directory / "TestFindBiRectangleConstrainedDesignSingleUTube"
        ghe.prepare_results("Project Name", "Notes", "Author", "Iteration Name")
        ghe.write_output_files(output_file_directory, "")
        u_tube_height = ghe.results.output_dict['ghe_system']['active_borehole_length']['value']
        self.assertAlmostEqual(133.24, u_tube_height, delta=0.01)
        nbh = ghe.results.borehole_location_data_rows  # includes a header row
        self.assertEqual(76 + 1, len(nbh))

    def test_double_u_tube(self):
        ghe = GHEManager()
        ghe.set_double_u_tube_pipe_parallel(
            inner_diameter=0.0216, outer_diameter=0.02667, shank_spacing=0.0323,
            roughness=1.0e-6, conductivity=0.4, rho_cp=1542000.0)
        ghe.set_soil(conductivity=2.0, rho_cp=2343493.0, undisturbed_temp=18.3)
        ghe.set_grout(conductivity=1.0, rho_cp=3901000.0)
        ghe.set_fluid()
        ghe.set_borehole(height=96.0, buried_depth=2.0, diameter=0.150)
        ghe.set_simulation_parameters(num_months=240, max_eft=35, min_eft=5, max_height=135, min_height=60)
        ghe.set_ground_loads_from_hourly_list(self.get_atlanta_loads())
        ghe.set_geometry_constraints_bi_rectangle_constrained(
            b_min=5.0, b_max_x=25.0, b_max_y=25.0,
            property_boundary=prop_boundary, no_go_boundaries=no_go_zones)
        ghe.set_design(flow_rate=0.2, flow_type_str="borehole")
        ghe.find_design()
        output_file_directory = self.test_outputs_directory / "TestFindBiRectangleConstrainedDesignDoubleUTube"
        ghe.prepare_results("Project Name", "Notes", "Author", "Iteration Name")
        ghe.write_output_files(output_file_directory, "")
        u_tube_height = ghe.results.output_dict['ghe_system']['active_borehole_length']['value']
        self.assertAlmostEqual(133.31, u_tube_height, delta=0.01)
        nbh = ghe.results.borehole_location_data_rows  # includes a header row
        self.assertEqual(69 + 1, len(nbh))

    def test_coaxial(self):
        ghe = GHEManager()
        ghe.set_coaxial_pipe(
            inner_pipe_d_in=0.0442, inner_pipe_d_out=0.050, outer_pipe_d_in=0.0974, outer_pipe_d_out=0.11,
            roughness=1.0e-6, conductivity_inner=0.4, conductivity_outer=0.4, rho_cp=1542000.0)
        ghe.set_soil(conductivity=2.0, rho_cp=2343493.0, undisturbed_temp=18.3)
        ghe.set_grout(conductivity=1.0, rho_cp=3901000.0)
        ghe.set_fluid()
        ghe.set_borehole(height=96.0, buried_depth=2.0, diameter=0.150)
        ghe.set_simulation_parameters(num_months=240, max_eft=35, min_eft=5, max_height=135, min_height=60)
        ghe.set_ground_loads_from_hourly_list(self.get_atlanta_loads())
        ghe.set_geometry_constraints_bi_rectangle_constrained(
            b_min=5.0, b_max_x=25.0, b_max_y=25.0,
            property_boundary=prop_boundary, no_go_boundaries=no_go_zones)
        ghe.set_design(flow_rate=0.2, flow_type_str="borehole")
        ghe.find_design()
        output_file_directory = self.test_outputs_directory / "TestFindBiRectangleConstrainedDesignCoaxial"
        ghe.prepare_results("Project Name", "Notes", "Author", "Iteration Name")
        ghe.write_output_files(output_file_directory, "")
        u_tube_height = ghe.results.output_dict['ghe_system']['active_borehole_length']['value']
        self.assertAlmostEqual(132.93, u_tube_height, delta=0.01)
        nbh = ghe.results.borehole_location_data_rows  # includes a header row
        self.assertEqual(74 + 1, len(nbh))
