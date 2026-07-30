import streamlit as st
from color_engine_web import calculate_lab

st.title("ICC CMYK to L*a*b* Predictor")

# File upload widget
uploaded_icc = st.file_uploader("Upload Press Profile (.icc)", type=["icc", "icm"])

# Input fields
c = st.number_input("Cyan (%)", min_value=0.0, max_value=100.0)
m = st.number_input("Magenta (%)", min_value=0.0, max_value=100.0)
y = st.number_input("Yellow (%)", min_value=0.0, max_value=100.0)
k = st.number_input("Black (%)", min_value=0.0, max_value=100.0)
# ... (Y and K)

if st.button("Predict L*a*b*"):
    if uploaded_icc is not None:
        # Streamlit handles the uploaded file securely in memory
        results = calculate_lab(uploaded_icc, c, m, y, k)
        
        st.write("### Predicted Color")
        st.write(f"**L*:** {results['L']:.2f}")
        st.write(f"**a*:** {results['a']:.2f}")
        st.write(f"**b*:** {results['b']:.2f}")
    else:
        st.error("Please upload an ICC profile first.")