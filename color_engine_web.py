from icc_parser_web import ICCParser 
import numpy as np

def calculate_lab(icc_path, c, m, y, k):
    # 1. Initialize your parser with the uploaded profile
    parser = ICCParser(icc_path)
    
    # 2. Convert the 0-100 CMYK inputs from the UI into 0.0 - 1.0 floats 
    # (Assuming your evaluate_cmyk method expects normalized values!)
    c_norm = c / 100.0
    m_norm = m / 100.0
    y_norm = y / 100.0
    k_norm = k / 100.0
    
    # 3. Shape it into the 1x4 array your method expects
    cmyk_array = np.array([[c_norm, m_norm, y_norm, k_norm]])
    
    # 4. Push it through your existing A2B1 method
    a2b1_results = parser.evaluate_cmyk(cmyk_array)
    
    # 5. Extract the Lab values
    # (Check if your method returns 'Lab_abs' or just 'Lab' depending on how you wrote it)
    predicted_lab = a2b1_results['Lab_abs'][0] 
    
    # 6. Return the dictionary to app.py
    return {
        'L': predicted_lab[0],
        'a': predicted_lab[1],
        'b': predicted_lab[2]
    }

def check_gamut(icc_path, L, a, b):
    # Pass the Streamlit buffer directly;
    parser = ICCParser(icc_path)
    
    # Run the gamut check
    results = parser.check_color_gamut(L, a, b)
    
    return results