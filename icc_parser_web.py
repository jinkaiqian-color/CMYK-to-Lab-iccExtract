#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import struct
import os
import io
import numpy as np
import pandas as pd

class ICCParser:
    def __init__(self, filepath_or_buffer):
        self.header = {}
        self.tag_table = {}
        self.parsed_tags = {}
        self.raw_data = None
        
        # Check if it's a string path (local file)
        if isinstance(filepath_or_buffer, str):
            self.filepath = filepath_or_buffer
            if not os.path.exists(self.filepath):
                raise FileNotFoundError(f"Cannot find {self.filepath}")
            with open(self.filepath, 'rb') as f:
                self.raw_data = f.read()
                
        # Otherwise, treat it as a web upload buffer (Streamlit)
        else:
            self.filepath = "Web_Upload"
            filepath_or_buffer.seek(0)
            self.raw_data = filepath_or_buffer.read()
            
        # Parse the data now that it's loaded
        if self.raw_data:
            self._parse_header()
            self._parse_tag_table()

    def _parse_file(self):
        with open(self.filepath, 'rb') as f:
            self.raw_data = f.read()

        self._parse_header()
        self._parse_tag_table()

    def _parse_header(self):
        """Extracts the 128-byte ICC profile header."""
        self.header['size'] = struct.unpack('>I', self.raw_data[0:4])[0]
        self.header['cmm_type'] = struct.unpack('>4s', self.raw_data[4:8])[0].decode('ascii', errors='ignore').strip()

        version_raw = struct.unpack('>I', self.raw_data[8:12])[0]
        self.header['version'] = f"{(version_raw >> 24) & 0xFF}.{(version_raw >> 20) & 0x0F}.{(version_raw >> 16) & 0x0F}"

        self.header['device_class'] = struct.unpack('>4s', self.raw_data[12:16])[0].decode('ascii').strip()
        self.header['color_space'] = struct.unpack('>4s', self.raw_data[16:20])[0].decode('ascii').strip()
        self.header['pcs'] = struct.unpack('>4s', self.raw_data[20:24])[0].decode('ascii').strip()

        magic = struct.unpack('>4s', self.raw_data[36:40])[0]
        if magic != b'acsp':
            raise ValueError("Invalid ICC Profile: Missing 'acsp' magic number.")
        # Color Space Guardrail
        if self.header['color_space'] != 'CMYK':
            raise ValueError(f"Unsupported Profile: Parser currently requires 'CMYK', but found '{self.header['color_space']}'.")


    def _parse_tag_table(self):
        """Reads the table of contents to map out where every tag lives."""
        tag_count = struct.unpack('>I', self.raw_data[128:132])[0]

        for i in range(tag_count):
            start = 132 + (i * 12)
            sig, offset, size = struct.unpack('>4sII', self.raw_data[start:start+12])

            tag_name = sig.decode('ascii', errors='ignore').strip()
            self.tag_table[tag_name] = {
                'offset': offset,
                'size': size
            }

    def print_summary(self):
        print(f"--- Profile: {os.path.basename(self.filepath)} ---")
        print(f"Version: {self.header['version']}")
        print(f"Device Class: {self.header['device_class']}")
        print(f"Color Space: {self.header['color_space']} -> {self.header['pcs']}")
        print(f"Total Tags: {len(self.tag_table)}")
        tag_names = ",".join(self.tag_table.keys())
        print(f"Tag names are: {tag_names}") 


    def get_tag_data(self, tag_name):
        if tag_name not in self.tag_table:
            return None

        tag_offset = self.tag_table[tag_name]['offset']
        tag_type = self._read_tag_type(tag_offset)

        if tag_type == 'mAB ':
            # FIXED: Pass the byte slice starting from the offset, not the integer
            return self._parse_mab_type(self.raw_data[tag_offset:]) 

        elif tag_type == 'mBA ':
            return self._parse_mba_type(self.raw_data[tag_offset:])

        elif tag_type == 'mft2':
            # mft2 is designed to accept the offset integer
            return self._parse_mft2(tag_offset, tag_name)

        elif tag_type == 'XYZ ':
            # NEW: Wire up your existing XYZ parser, passing the byte slice!
            return self._parse_xyz_type(self.raw_data[tag_offset:])

        else:
            print(f"Warning: Parser for type '{tag_type}' not yet implemented.")
            return tag_type

    def _read_tag_type(self, offset):
        """
        直接从内存中的 raw_data 读取 4 字节的 Tag Type 签名，避免重复打开文件。
        """
        # 从指定偏移量切片提取 4 个字节
        tag_type_bytes = self.raw_data[offset : offset + 4]

        # 解码为字符串并返回
        return tag_type_bytes.decode('ascii', errors='ignore')


    def _parse_xyz_type(self, raw_bytes):
        """Decodes standard ICC XYZ coordinates (s15Fixed16Number)."""
        x_raw, y_raw, z_raw = struct.unpack('>iii', raw_bytes[8:20])
        return [x_raw / 65536.0, y_raw / 65536.0, z_raw / 65536.0]

    def _parse_curve_sequence(self, raw_tag_bytes, start_offset, num_curves):
        """Extracts a sequential block of curves (curv or para)."""
        if start_offset == 0:
            return None 

        curves = []
        current_offset = start_offset

        for i in range(num_curves):
            sig = struct.unpack('>4s', raw_tag_bytes[current_offset:current_offset+4])[0]

            if sig == b'curv':
                count = struct.unpack('>I', raw_tag_bytes[current_offset+8:current_offset+12])[0]
                if count == 0:
                    curve_data = {'type': 'identity'}
                    actual_size = 12
                elif count == 1:
                    gamma_raw = struct.unpack('>H', raw_tag_bytes[current_offset+12:current_offset+14])[0]
                    curve_data = {'type': 'gamma', 'gamma': gamma_raw / 256.0}
                    actual_size = 14
                else:
                    format_string = f'>{count}H'
                    data_offset = current_offset + 12
                    points = struct.unpack(format_string, raw_tag_bytes[data_offset : data_offset + (count * 2)])
                    curve_data = {'type': 'sampled', 'points': [p / 65535.0 for p in points]}
                    actual_size = 12 + (count * 2)

            elif sig == b'para':
                func_type = struct.unpack('>H', raw_tag_bytes[current_offset+8:current_offset+10])[0]
                param_counts = {0: 1, 1: 3, 2: 4, 3: 5, 4: 7}
                p_count = param_counts.get(func_type, 0)
                format_string = f'>{p_count}i'
                data_offset = current_offset + 12
                raw_params = struct.unpack(format_string, raw_tag_bytes[data_offset : data_offset + (p_count * 4)])
                params = [p / 65536.0 for p in raw_params]
                curve_data = {'type': 'parametric', 'func_type': func_type, 'params': params}
                actual_size = 12 + (p_count * 4)
            else:
                raise ValueError(f"Unknown curve signature: {sig}")

            curves.append(curve_data)
            padded_size = (actual_size + 3) & ~3
            current_offset += padded_size

        return curves

    def _parse_matrix(self, raw_bytes, offset):
        """
        Extracts the 3x4 matrix from an mAB/mBA tag.
        Values are stored sequentially as 12 s15Fixed16Number values (48 bytes).
        """
        if offset == 0:
            return None

        # Unpack 12 consecutive 4-byte signed integers (48 bytes total)
        raw_values = struct.unpack('>12i', raw_bytes[offset:offset+48])

        # Convert fixed-point to float
        floats = [val / 65536.0 for val in raw_values]

        # Structure as a 3x4 array: [3x3 Matrix | 1D Offset]
        # Row 1: [M11, M12, M13, Offset1]
        # Row 2: [M21, M22, M23, Offset2]
        # Row 3: [M31, M32, M33, Offset3]
        return [
            [floats[0], floats[1], floats[2], floats[9]],
            [floats[3], floats[4], floats[5], floats[10]],
            [floats[6], floats[7], floats[8], floats[11]]
        ]

    def _parse_mab_type(self, raw_bytes):
        """Decodes the header and sub-elements of an mAB tag (Device to PCS) and maps channels."""
        input_channels, output_channels = struct.unpack('>BB', raw_bytes[8:10])
        b_off, mat_off, m_off, clut_off, a_off = struct.unpack('>IIIII', raw_bytes[12:32])

        # Extract Sequences
        a_curves_list = self._parse_curve_sequence(raw_bytes, a_off, input_channels)
        m_curves_list = self._parse_curve_sequence(raw_bytes, m_off, output_channels)
        b_curves_list = self._parse_curve_sequence(raw_bytes, b_off, output_channels)

        # Extract Matrix (if present)
        matrix_data = None
        if mat_off != 0 and hasattr(self, '_parse_matrix'):
            matrix_data = self._parse_matrix(raw_bytes, mat_off)

        # Extract the CLUT Grid
        clut_data = self._parse_clut(raw_bytes, clut_off, input_channels, output_channels)

        # --- Mapping Logic ---
        mapped_a_curves = {}
        if a_curves_list:
            if input_channels == 4 and self.header.get('color_space') == 'CMYK':
                mapped_a_curves = {'C': a_curves_list[0], 'M': a_curves_list[1], 
                                   'Y': a_curves_list[2], 'K': a_curves_list[3]}
            else:
                mapped_a_curves = {f'Channel_{i}': curve for i, curve in enumerate(a_curves_list)}

        mapped_m_curves = {}
        if m_curves_list:
            mapped_m_curves = {f'Channel_{i}': curve for i, curve in enumerate(m_curves_list)}

        mapped_b_curves = {}
        if b_curves_list:
            mapped_b_curves = {f'Channel_{i}': curve for i, curve in enumerate(b_curves_list)}

        return {
            'type': 'mAB',
            'input_channels': input_channels,
            'output_channels': output_channels,
            'offsets': {
                'A_curves': a_off, 'CLUT': clut_off, 'M_curves': m_off, 
                'Matrix': mat_off, 'B_curves': b_off
            },
            'data': {
                'A_curves': mapped_a_curves,
                'A_curves_raw': a_curves_list,
                'CLUT': clut_data,
                'M_curves_raw': mapped_m_curves,
                'Matrix': matrix_data,
                'B_curves': mapped_b_curves
            }
        }

    def _parse_mba_type(self, raw_bytes):
        """Decodes the header and sub-elements of an mBA tag (PCS to Device) and maps channels."""
        input_channels, output_channels = struct.unpack('>BB', raw_bytes[8:10])

        # Unpack the 5 offset pointers in their exact order
        b_off, mat_off, m_off, clut_off, a_off = struct.unpack('>IIIII', raw_bytes[12:32])

        # 1. Extract B Curves (PCS space, input from Lab/XYZ)
        b_curves_list = self._parse_curve_sequence(raw_bytes, b_off, input_channels)

        # 2. Extract Matrix (3x4 Matrix)
        matrix_data = None 
        if mat_off > 0:
            matrix_data = self._parse_matrix(raw_bytes, mat_off)

        # 3. Extract M Curves (PostShaper, applied before CLUT in B2A)
        m_curves_list = self._parse_curve_sequence(raw_bytes, m_off, input_channels)

        # 4. Extract the CLUT Grid
        clut_data = self._parse_clut(raw_bytes, clut_off, input_channels, output_channels)

        # 5. Extract A Curves (Device space, final output mapping)
        a_curves_list = self._parse_curve_sequence(raw_bytes, a_off, output_channels)

        # Map the output to the standard C, M, Y, K sequence
        mapped_a_curves = {}
        if a_curves_list:
            if output_channels == 4 and self.header.get('color_space') == 'CMYK':
                mapped_a_curves = {'C': a_curves_list[0], 'M': a_curves_list[1], 'Y': a_curves_list[2], 'K': a_curves_list[3]}
            else:
                mapped_a_curves = {f'Channel_{i}': curve for i, curve in enumerate(a_curves_list)}

        return {
            'type': 'mBA',
            'input_channels': input_channels,
            'output_channels': output_channels,
            'offsets': {
                'B_curves': b_off,
                'Matrix': mat_off,
                'M_curves': m_off,
                'CLUT': clut_off,
                'A_curves': a_off
            },
            'data': {
                'B_curves': b_curves_list,
                'Matrix': matrix_data,
                'M_curves': m_curves_list,
                'CLUT': clut_data,
                'A_curves': mapped_a_curves,
                'A_curves_raw': a_curves_list
            }
        }

    def _parse_mft2(self, offset, tag_name):
        """
        专门解析 ICC v2 配置文件中的 mft2 (lut16Type) 标签，
        并将其映射为 v4 的 AToB / BToA 字典格式。
        """

        # 使用 io.BytesIO 将内存中的 raw_data 包装成像文件一样的对象
        f = io.BytesIO(self.raw_data)
        f.seek(offset)

        # 1. 读取基础头部信息
        tag_sig = f.read(4).decode('ascii', errors='ignore') # 'mft2'
        f.read(4) # 忽略 4 bytes 保留字
        in_ch, out_ch, grid_points, _pad = struct.unpack('>BBBB', f.read(4))

        # 2. 读取 3x3 矩阵 (9 个 s15Fixed16 格式的数据)
        matrix_raw = struct.unpack('>9i', f.read(36))
        m = [x / 65536.0 for x in matrix_raw]
        # ICC v2 矩阵没有 Offset，为了匹配 v4 的 3x4 格式，我们在末尾补零
        matrix_data = [
            [m[0], m[1], m[2], 0.0],
            [m[3], m[4], m[5], 0.0],
            [m[6], m[7], m[8], 0.0]
        ]

        # 3. 读取输入和输出曲线的控制点数量
        in_entries, out_entries = struct.unpack('>HH', f.read(4))

        # --- 辅助方法：读取 16位 (uint16) 曲线数据 ---
        def read_curves(num_channels, num_entries):
            curves = {}
            for c in range(num_channels):
                data = struct.unpack('>' + 'H' * num_entries, f.read(2 * num_entries))
                normalized = [x / 65535.0 for x in data]
                curve_dict = {'type': 'sampled', 'points': normalized}

                # Assign exact channel keys without generic duplicates
                if num_channels == 4:
                    # Restored to standard CMYK for general profile parsing
                    curves[['C', 'M', 'Y', 'K'][c]] = curve_dict
                elif num_channels == 3:
                    curves[['L', 'a', 'b'][c]] = curve_dict
                else:
                    curves[f'Channel_{c}'] = curve_dict
            return curves

        # 4. 读取 Input Tables (输入曲线)
        input_tables = read_curves(in_ch, in_entries)

        # 5. 读取 CLUT (多维查找表)
        num_clut_points = (grid_points ** in_ch) * out_ch
        clut_raw = struct.unpack('>' + 'H' * num_clut_points, f.read(2 * num_clut_points))
        clut_grid = np.array(clut_raw) / 65535.0

        # 重塑 CLUT 形状
        shape = [grid_points] * in_ch + [out_ch]
        clut_grid = clut_grid.reshape(shape)

        # 6. 读取 Output Tables (输出曲线)
        output_tables = read_curves(out_ch, out_entries)

        # ==========================================================
        # 7. 终极转换：将 v2 扁平化数据封装成 v4 格式
        # ==========================================================
        data_dict = {}
        if tag_name.startswith('A2B'): 
            data_dict['A_curves'] = input_tables
            data_dict['CLUT'] = {'dimensions': [grid_points]*in_ch, 'grid': clut_grid}
            data_dict['M_curves'] = output_tables
            data_dict['Matrix']   = matrix_data
            data_dict['B_curves'] = None
        else:
            data_dict['B_curves'] = input_tables
            data_dict['Matrix']   = matrix_data
            data_dict['M_curves'] = None
            data_dict['CLUT'] = {'dimensions': [grid_points]*in_ch, 'grid': clut_grid}
            data_dict['A_curves'] = output_tables

        return {
            'type': tag_sig,
            'input_channels': in_ch,
            'output_channels': out_ch,
            'data': data_dict
        }

    def _parse_clut(self, raw_tag_bytes, start_offset, input_channels, output_channels):
        """Extracts the multi-dimensional CLUT grid dynamically based on profile headers."""
        if start_offset == 0:
            return None 

        # 1. Read the 16 bytes reserved for grid dimensions
        raw_dims = struct.unpack('>16B', raw_tag_bytes[start_offset : start_offset + 16])

        # 2. Only take the dimensions corresponding to the number of input channels
        # If input_channels is 4 (CMYK), we only care about the first 4 bytes.
        actual_dims = tuple(raw_dims[:input_channels])

        # 3. Precision is at byte 16 of the CLUT tag (relative to start_offset)
        precision = struct.unpack('>B', raw_tag_bytes[start_offset + 16 : start_offset + 17])[0]

        # 4. Data begins at byte 20 of the CLUT tag
        data_offset = start_offset + 20

        # 5. Calculate total elements based on dynamic dimensions
        total_nodes = np.prod(actual_dims)
        total_values = total_nodes * output_channels

        # 6. Extract data with dynamic precision handling
        if precision == 1: # 8-bit
            buffer = raw_tag_bytes[data_offset : data_offset + total_values]
            raw_array = np.frombuffer(buffer, dtype=np.uint8)
            normalized_array = raw_array.astype(float) / 255.0
        elif precision == 2: # 16-bit
            buffer = raw_tag_bytes[data_offset : data_offset + (total_values * 2)]
            raw_array = np.frombuffer(buffer, dtype='>u2')
            normalized_array = raw_array.astype(float) / 65535.0
        else:
            raise ValueError(f"Unknown CLUT precision: {precision}")

        return {
            'dimensions': actual_dims,
            'precision': precision, # Added this back just in case
            'shape': normalized_array.reshape(actual_dims + (output_channels,)).shape, # ADD THIS KEY
            'grid': normalized_array.reshape(actual_dims + (output_channels,))
        }

    @staticmethod
    def decode_lab(normalized_lab):
        """
        Decodes 16-bit normalized Lab values (0.0 - 1.0) to true L*a*b* values.
        Expects an iterable (list, tuple, or numpy array) of 3 floats.
        """
        l_star = normalized_lab[0] * 100.0
        a_star = (normalized_lab[1] * 255.0) - 128.0
        b_star = (normalized_lab[2] * 255.0) - 128.0

        return l_star, a_star, b_star

    @staticmethod
    def lab_to_xyz_d50(lab_array):
        """Standard CIELAB to XYZ D50 conversion."""
        L, a, b = lab_array[:, 0], lab_array[:, 1], lab_array[:, 2]
        fy = (L + 16.0) / 116.0
        fx = a / 500.0 + fy
        fz = fy - b / 200.0

        xr = np.where(fx**3 > 0.008856, fx**3, (116.0 * fx - 16.0) / 903.3)
        yr = np.where(L > 8.0, fy**3, L / 903.3)
        zr = np.where(fz**3 > 0.008856, fz**3, (116.0 * fz - 16.0) / 903.3)

        return np.column_stack((xr * 0.9642, yr * 1.0000, zr * 0.8249))

    @staticmethod
    def xyz_to_lab_d50(xyz_array):
        """Standard XYZ to CIELAB D50 conversion."""
        xr, yr, zr = xyz_array[:, 0] / 0.9642, xyz_array[:, 1] / 1.0000, xyz_array[:, 2] / 0.8249

        fx = np.where(xr > 0.008856, np.cbrt(xr), (903.3 * xr + 16.0) / 116.0)
        fy = np.where(yr > 0.008856, np.cbrt(yr), (903.3 * yr + 16.0) / 116.0)
        fz = np.where(zr > 0.008856, np.cbrt(zr), (903.3 * zr + 16.0) / 116.0)

        L = np.where(yr > 0.008856, 116.0 * np.cbrt(yr) - 16.0, 903.3 * yr)
        a = 500.0 * (fx - fy)
        b = 200.0 * (fy - fz)

        return np.column_stack((L, a, b))

    @staticmethod
    def generate_channel_ramp(channel_idx, steps=11):
        """Generates a CMYK array from 0.0 to 1.0 for a specific channel index."""
        ramp = np.zeros((steps, 4))
        ramp[:, channel_idx] = np.linspace(0.0, 1.0, steps)
        return ramp

    @staticmethod
    def calculate_icc_tvi(xyz_values, nominal_percentages, channel):
        """Calculates ISO 10128 Colorimetric TVI directly from XYZ arrays."""
        if channel == 'C':
            R_values = xyz_values[:, 0] - (0.55 * xyz_values[:, 2]) # Cyan X-correction
        elif channel == 'M' or channel == 'K':
            R_values = xyz_values[:, 1] # M and K use Y
        elif channel == 'Y':
            R_values = xyz_values[:, 2] # Y uses Z
        else:
            raise ValueError("Channel must be 'C', 'M', 'Y', or 'K'")

        R_p = R_values[0] 
        R_s = R_values[-1]

        tone_values = 100.0 * (R_p - R_values) / (R_p - R_s)
        tvi_values = tone_values - nominal_percentages

        results = pd.DataFrame({
            f'{channel}_Input_%': nominal_percentages,
            'Tone_Value_%': tone_values,
            'TVI_%': tvi_values
        })
        return results.round(2)

    def get_tvi_curve(self, channel, steps=11):
        """
        Master method to generate a TVI curve directly from the ICC profile.
        Automatically handles the ramp generation, ICC evaluation, and TVI math.
        """
        # 1. Map the string channel to its numeric index
        channel_map = {'C': 0, 'M': 1, 'Y': 2, 'K': 3}
        if channel not in channel_map:
            raise ValueError("Channel must be 'C', 'M', 'Y', or 'K'")

        channel_idx = channel_map[channel]

        # 2. Generate the CMYK ramp (calling the static method)
        ramp_cmyk = self.generate_channel_ramp(channel_idx, steps)

        # 3. Evaluate the ramp through the profile's pipeline
        evaluation_results = self.evaluate_cmyk(ramp_cmyk)
        ramp_xyz = evaluation_results['XYZ_abs']

        # 4. Generate the nominal percentages
        percentages = np.linspace(0.0, 100.0, steps)

        # 5. Calculate and return the final TVI DataFrame
        return self.calculate_icc_tvi(ramp_xyz, percentages, channel)

    def evaluate_cmyk(self, cmyk_array):
        """
        Passes an Nx4 CMYK array through the A2B1 pipeline and outputs all color stages.
        Returns a dictionary with Relative Lab, Absolute XYZ, and Absolute Lab.
        """
        # ... [Keep all the vectorized interpolation code from Steps 1-3 exactly the same] ...
        a2b1 = self.get_tag_data('A2B1')
        a_curves = a2b1['data']['A_curves']
        clut = a2b1['data']['CLUT']
        grid_nodes = clut['dimensions'][0]
        clut_grid = clut['grid']

        # Helper function for 1D curves nested inside
        def apply_1d(inputs, curve_data):
            if curve_data['type'] == 'identity':
                return inputs
            elif curve_data['type'] == 'sampled':
                pts = np.array(curve_data['points'])
                return np.interp(inputs, np.linspace(0, 1, len(pts)), pts)
            return inputs

        # 1. A-Curves (Input Linearization)
        lin_C = apply_1d(cmyk_array[:, 0], a_curves['C'])
        lin_M = apply_1d(cmyk_array[:, 1], a_curves['M'])
        lin_Y = apply_1d(cmyk_array[:, 2], a_curves['Y'])
        lin_K = apply_1d(cmyk_array[:, 3], a_curves['K'])

        # 2. Multi-Dimensional Interpolation (Vectorized)
        input_coords = np.column_stack((lin_C, lin_M, lin_Y, lin_K))
        idx_float = input_coords * (grid_nodes - 1)
        idx_int = np.floor(idx_float).astype(int)
        frac = idx_float - idx_int

        mask = (idx_int == grid_nodes - 1)
        idx_int[mask] = grid_nodes - 2
        frac[mask] = 1.0

        sort_order = np.argsort(-frac, axis=1)
        f_sort = np.take_along_axis(frac, sort_order, axis=1)

        w0 = 1.0 - f_sort[:, 0]
        w1 = f_sort[:, 0] - f_sort[:, 1]
        w2 = f_sort[:, 1] - f_sort[:, 2]
        w3 = f_sort[:, 2] - f_sort[:, 3]
        w4 = f_sort[:, 3]

        v0 = idx_int.copy()
        v1, v2, v3, v4 = v0.copy(), v0.copy(), v0.copy(), v0.copy()

        # Fast Vectorized Incrementing (No for-loops!)
        rows = np.arange(cmyk_array.shape[0])
        v1[rows, sort_order[:, 0]] += 1
        v2[rows, sort_order[:, 0]] += 1
        v2[rows, sort_order[:, 1]] += 1
        v3[rows, sort_order[:, 0]] += 1
        v3[rows, sort_order[:, 1]] += 1
        v3[rows, sort_order[:, 2]] += 1
        v4 += 1

        c0 = clut_grid[v0[:,0], v0[:,1], v0[:,2], v0[:,3]]
        c1 = clut_grid[v1[:,0], v1[:,1], v1[:,2], v1[:,3]]
        c2 = clut_grid[v2[:,0], v2[:,1], v2[:,2], v2[:,3]]
        c3 = clut_grid[v3[:,0], v3[:,1], v3[:,2], v3[:,3]]
        c4 = clut_grid[v4[:,0], v4[:,1], v4[:,2], v4[:,3]]

        raw_lab = (c0 * w0[:, np.newaxis] + c1 * w1[:, np.newaxis] + 
                   c2 * w2[:, np.newaxis] + c3 * w3[:, np.newaxis] + c4 * w4[:, np.newaxis])
        raw_L, raw_a, raw_b = raw_lab[:, 0], raw_lab[:, 1], raw_lab[:, 2]

       # 3. 输出曲线处理 (V2 的 M_curves 或 V4 的 B_curves) 
        # 处理 V2 专用的 Output Tables (存储在 M_curves)
        if 'M_curves' in a2b1['data'] and a2b1['data']['M_curves']:
            m_curves = a2b1['data']['M_curves']
            if 'L' in m_curves: # V2 mft2 我们映射成了 L, a, b
                raw_L = apply_1d(raw_L, m_curves['L'])
                raw_a = apply_1d(raw_a, m_curves['a'])
                raw_b = apply_1d(raw_b, m_curves['b'])

        # 处理 V4 专用的 B_curves
        if 'B_curves' in a2b1['data'] and a2b1['data']['B_curves']:
            b_curves = a2b1['data']['B_curves']
            if 'Channel_0' in b_curves:
                raw_L = apply_1d(raw_L, b_curves['Channel_0'])
                raw_a = apply_1d(raw_a, b_curves['Channel_1'])
                raw_b = apply_1d(raw_b, b_curves['Channel_2'])

        # 4. PCS Decoding (Relative Lab)
        batch_Lab_Rel = np.column_stack((raw_L * 100.0, (raw_a * 255.0) - 128.0, (raw_b * 255.0) - 128.0))

        # 5. Absolute Colorimetric Conversion (XYZ)
        xyz_rel = self.lab_to_xyz_d50(batch_Lab_Rel) 

        wtpt = np.array(self.get_tag_data('wtpt'))
        media_white = wtpt / 100.0 if wtpt[1] > 1.0 else wtpt
        D50_XYZ = np.array([0.9642, 1.0000, 0.8249])

        xyz_abs = xyz_rel * (media_white / D50_XYZ)

        # 6. Convert Absolute XYZ back to Absolute Lab
        batch_Lab_Abs = self.xyz_to_lab_d50(xyz_abs)

        # Return all stages so the user can grab exactly what they need!
        return {
            'Lab_rel': batch_Lab_Rel,
            'XYZ_abs': xyz_abs,
            'Lab_abs': batch_Lab_Abs
        }

    def check_color_gamut(self, L, a, b):
        """
        Takes a target Lab value, predicts the closest CMYK recipe using B2A1,
        and verifies it by running the CMYK back through A2B1 to check gamut clipping.
        Uses pure NumPy vectorized 3D interpolation (No SciPy).
        """

        # ==========================================
        # STEP 1: PCS to Device (B2A1 Transform)
        # ==========================================
        b2a1 = self.get_tag_data('B2A1')
        b_curves = b2a1['data'].get('B_curves')
        matrix_data = b2a1['data'].get('Matrix')
        m_curves = b2a1['data'].get('M_curves')
        clut = b2a1['data']['CLUT']
        a_curves = b2a1['data']['A_curves'] # Mapped to 'C', 'M', 'Y', 'K'
        # New
        # --- ABSOLUTE TO RELATIVE SCALING ---
        # 1. Convert input Absolute Lab to Absolute XYZ
        input_lab_array = np.array([[L, a, b]])
        xyz_abs = self.lab_to_xyz_d50(input_lab_array)

        # 2. Fetch media white point and D50 reference
        wtpt = np.array(self.get_tag_data('wtpt'))
        media_white = wtpt / 100.0 if wtpt[1] > 1.0 else wtpt
        D50_XYZ = np.array([0.9642, 1.0000, 0.8249])

        # 3. Scale Absolute XYZ to Relative XYZ
        xyz_rel = xyz_abs * (D50_XYZ / media_white)

        # 4. Convert Relative XYZ back to Relative Lab
        lab_rel = self.xyz_to_lab_d50(xyz_rel)[0]

        L_norm = lab_rel[0] / 100.0
        a_norm = (lab_rel[1] + 128.0) / 255.0
        b_norm = (lab_rel[2] + 128.0) / 255.0
        pcs = np.array([L_norm, a_norm, b_norm])
        # New
        '''
        # Normalize Lab to standard ICC 0.0 - 1.0 range
        L_norm = L / 100.0
        a_norm = (a + 128.0) / 255.0
        b_norm = (b + 128.0) / 255.0
        pcs = np.array([L_norm, a_norm, b_norm])
        '''
        # Helper to apply 1D curves (identity or sampled)
        def apply_1d(val, curve_data):
            if curve_data is None or curve_data['type'] == 'identity':
                return val
            if curve_data['type'] == 'sampled':
                pts = np.array(curve_data['points'])
                return np.interp(val, np.linspace(0, 1, len(pts)), pts)
            return val

        def apply_curves_list(data_array, curves_list):
            if not curves_list: return data_array
            # Ensure we iterate correctly if the parser returns a dictionary instead of a list
            if isinstance(curves_list, dict):
                curves = list(curves_list.values())
            else:
                curves = curves_list
            return np.array([apply_1d(val, curve) for val, curve in zip(data_array, curves)])

        # 1. Apply B-Curves
        stage1 = apply_curves_list(pcs, b_curves)

        # 2. Apply 3x4 Matrix (if present)
        if matrix_data is not None:
            mat = np.array(matrix_data)
            M3x3 = mat[:, :3]
            offsets = mat[:, 3]
            stage2 = np.dot(M3x3, stage1) + offsets
        else:
            stage2 = stage1

        # 3. Apply M-Curves (PostShaper)
        stage3 = apply_curves_list(stage2, m_curves)

        # ==========================================
        # STEP 2: 3D Vectorized Interpolation (Option 2)
        # ==========================================
        grid_nodes = clut['dimensions'][0]
        clut_grid = clut['grid']

        # Convert the single 3-channel input into a 2D array (1x3) for vectorization
        lab_array = np.array([stage3])

        input_coords = lab_array 
        idx_float = input_coords * (grid_nodes - 1)
        idx_int = np.floor(idx_float).astype(int)
        frac = idx_float - idx_int

        # Boundary condition handling
        mask = (idx_int == grid_nodes - 1)
        idx_int[mask] = grid_nodes - 2
        frac[mask] = 1.0

        # Sort fractions for simplex calculation
        sort_order = np.argsort(-frac, axis=1)
        f_sort = np.take_along_axis(frac, sort_order, axis=1)

        # 4 Weights for 3D interpolation
        w0 = 1.0 - f_sort[:, 0]
        w1 = f_sort[:, 0] - f_sort[:, 1]
        w2 = f_sort[:, 1] - f_sort[:, 2]
        w3 = f_sort[:, 2]

        # 4 Vertices for 3D interpolation
        v0 = idx_int.copy()
        v1, v2, v3 = v0.copy(), v0.copy(), v0.copy()

        # Fast Vectorized Incrementing for 3D
        rows = np.arange(lab_array.shape[0])
        v1[rows, sort_order[:, 0]] += 1
        v2[rows, sort_order[:, 0]] += 1
        v2[rows, sort_order[:, 1]] += 1
        v3 += 1

        # Extract values from the 3D grid 
        c0 = clut_grid[v0[:,0], v0[:,1], v0[:,2]]
        c1 = clut_grid[v1[:,0], v1[:,1], v1[:,2]]
        c2 = clut_grid[v2[:,0], v2[:,1], v2[:,2]]
        c3 = clut_grid[v3[:,0], v3[:,1], v3[:,2]]

        # Calculate raw CMYK output
        raw_cmyk_batch = (c0 * w0[:, np.newaxis] + c1 * w1[:, np.newaxis] + 
                          c2 * w2[:, np.newaxis] + c3 * w3[:, np.newaxis])

        # Extract the single result from the batch array
        stage4 = raw_cmyk_batch[0]

        # ==========================================
        # STEP 3: Apply A-Curves (Device Linearization)
        # ==========================================
        c_val = apply_1d(stage4[0], a_curves['C'])
        m_val = apply_1d(stage4[1], a_curves['M'])
        y_val = apply_1d(stage4[2], a_curves['Y'])
        k_val = apply_1d(stage4[3], a_curves['K'])

        # Final raw CMYK recipe (0.0 to 1.0)
        cmyk_out = np.array([c_val, m_val, y_val, k_val])

        # ==========================================
        # STEP 4: Device to PCS (A2B1 Round-trip)
        # ==========================================
        # Reshape to 1x4 array so it works with your existing evaluate_cmyk method
        cmyk_array = cmyk_out.reshape(1, 4)

        # Push through your existing A2B1 method
        a2b1_results = self.evaluate_cmyk(cmyk_array)
        predicted_lab = a2b1_results['Lab_abs'][0] 

        # ==========================================
        # STEP 5: Gamut Logic & Console Output
        # ==========================================
        target_lab = np.array([L, a, b])

        # Calculate Delta Eab
        delta_e = np.linalg.norm(target_lab - predicted_lab)
        in_gamut = delta_e <= 1.0 

        cmyk_pct = np.round(cmyk_out * 100, 2)

        return {
            'in_gamut': in_gamut,
            'cmyk_percentages': cmyk_pct,
            'predicted_lab': predicted_lab,
            'delta_e': delta_e,
            'a_curves': a_curves # Return these so the Execution block can access them
        }

