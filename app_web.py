import streamlit as st
from color_engine_web import calculate_lab, check_gamut

st.title("ICC Color Engine Parser")

# File upload widget
uploaded_icc = st.file_uploader("Upload Press Profile (.icc)", type=["icc", "icm"])

st.divider()

# ==========================================
# TOOL 1: CMYK to Lab Predictor
# ==========================================
st.header("CMYK to L* a* b* Predictor")
# Input fields
c = st.number_input("Cyan (%)", min_value=0.0, max_value=100.0)
m = st.number_input("Magenta (%)", min_value=0.0, max_value=100.0)
y = st.number_input("Yellow (%)", min_value=0.0, max_value=100.0)
k = st.number_input("Black (%)", min_value=0.0, max_value=100.0)


if st.button("Predict L* a* b*"):
    if uploaded_icc is not None:
        # Reset stream position just in case
        uploaded_icc.seek(0)
        results = calculate_lab(uploaded_icc, c, m, y, k)
        
        st.write("### Predicted Color")
        st.write(f"**L*:** {results['L']:.2f}")
        st.write(f"**a*:** {results['a']:.2f}")
        st.write(f"**b*:** {results['b']:.2f}")
    else:
        st.error("Please upload an ICC profile first.")

st.divider()

# ==========================================
# TOOL 2: Lab Gamut Checker 
# ==========================================
st.header("Profile L* a* b* Gamut Checker")
st.write("Enter an L* a* b* color to see if it can be printed by this profile. Due to GCR used during profile generating procedure, CMYK to Lab roundtrip may not produce the same value!")

# Use columns to lay out the inputs nicely side-by-side
col1, col2, col3 = st.columns(3)
with col1:
    L_input = st.number_input("L*", min_value=0.0, max_value=100.0, value=50.0, step=0.1)
with col2:
    a_input = st.number_input("a*", min_value=-128.0, max_value=127.0, value=0.0, step=0.1)
with col3:
    b_input = st.number_input("b*", min_value=-128.0, max_value=127.0, value=0.0, step=0.1)

if st.button("Check Gamut"):
    if uploaded_icc is not None:
        # Crucial: Reset the file stream position to 0 
        uploaded_icc.seek(0) 
        
        # Call the new function from color_engine_web
        results = check_gamut(uploaded_icc, L_input, a_input, b_input)
        
        # Extract the CMYK array once to keep code clean
        cmyk = results['cmyk_percentages']
        
        # Display Results
        if results['in_gamut']:
            st.success(f"**Success!** Color is IN gamut. (ΔE: {results['delta_e']:.2f})")
            st.write("### CMYK Recipe:")
            st.info(f"**C:** {cmyk[0]}% | **M:** {cmyk[1]}% | **Y:** {cmyk[2]}% | **K:** {cmyk[3]}%")
        else:
            st.error(f"**Warning!** Color is OUT of gamut. (ΔE: {results['delta_e']:.2f})")
            st.write("### Closest Printable Match:")
            st.info(f"**C:** {cmyk[0]}% | **M:** {cmyk[1]}% | **Y:** {cmyk[2]}% | **K:** {cmyk[3]}%")
            
    else:
        st.error("Please upload an ICC profile first.")
