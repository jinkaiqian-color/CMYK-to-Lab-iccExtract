# CMYK to CIE L* a* b* Predictor

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://cmyk-to-lab-iccextract.streamlit.app/)

A lightweight web utility for color management and printing operations. This tool allows users to extract and predict accurate CIE L* a* b* colorimetric values from any user-supplied CMYK ICC press profile.

ECG profile compatibility is under construction.

## Live Demo
You can use the tool directly in your browser here: **[Launch ICC Color Engine Parser](https://cmyk-to-lab-iccextract.streamlit.app/)**

## How to Use
1. **Upload an ICC Profile:** Start by uploading any standard CMYK ICC profile (e.g., GRACoL, SWOP, Fogra, or a custom press profile). 
2. **Input CMYK Values:** Enter your desired target values for Cyan, Magenta, Yellow, and Black (ranging from 0% to 100%).
3. **Predict L*a*b*:** Click the predict button to calculate the exact L* a* b* color output based on the uploaded profile's colorimetric rendering intent.
4. **Input Lab values:** Enter your desired Lab target values and see if this color is within the color gamut of uploaded profile. Meanwhile, corresponding CMYK value will be calculated and displayed.


