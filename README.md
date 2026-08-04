# Extract data from your CMYK printer icc profile

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://cmyk-to-lab-iccextract.streamlit.app/)

A lightweight web utility for color management and printing operations. This tool allows users to extract and predict accurate CIE L* a* b* colorimetric values from any user-supplied CMYK ICC press profile. Or if you'd like to see a target L* a* b* is within the icc profile gamut or not.

ECG profile compatibility is under construction.

## Live Demo
You can use the tool directly in your browser here: **[Launch ICC Color Engine Parser](https://cmyk-to-lab-iccextract.streamlit.app/)**

## How to Use
1. **Upload an ICC Profile:** Start by uploading any standard CMYK ICC profile (e.g., GRACoL, SWOP, Fogra, or a custom press profile). 
2. **Input CMYK Values:** Enter your desired target values for Cyan, Magenta, Yellow, and Black (ranging from 0% to 100%).
3. **Predict L* a* b*:** Click the predict button to calculate the exact L* a* b* color output based on the uploaded profile's colorimetric rendering intent.
4. **Input L* a* b* values:** Enter your desired L* a* b* target values and see if this color is within the color gamut of uploaded profile. Meanwhile, corresponding CMYK value will be calculated and displayed.


## Understanding ICC Profile Conversions in This Engine 
To understand how this utility predicts color transformations, it is helpful to look under the hood at how ICC profiles handle color data. Specifically, this tool mathematically ensures Absolute Colorimetric precision by leveraging the A2B1, B2A1, and wtpt (Media White Point) tags defined in the ICC specification (ISO 15076-1).

**Why Absolute Colorimetric?**

In print production and proofing, we usually want to know the Absolute L* a* b* value, which includes the physical color of the paper substrate.In a perfect world, an ICC profile would contain **A2B3** and **B2A3** tags, which are specifically designated for Absolute Colorimetric conversions. However, because these tags are technically optional in the ICC specification, many CMYK press profiles completely omit them to save file size.To ensure universal compatibility across all profiles, this engine bypasses the need for the A2B3/B2A3 tags by using a highly accurate mathematical scaling technique.

**The Forward Pipeline (CMYK to Lab)**

When you input CMYK values into the predictor:
1. **Media-Relative Conversion (A2B1)**: The tool first passes the CMYK values through the A2B1 tag. This transforms the device CMYK into Media-Relative L* a* b* (where the paper is assumed to be perfectly white).
20. **White Point Scaling (wtpt)**: The engine reads the profile's Media White Point (wtpt tag). It converts the relative color to the XYZ color space, multiplies it by the ratio of the physical media white point to the D50 standard illuminant, and converts it back.
21. **Result**: This manual conversion yields an accurate Absolute L* a* b* value, accurately simulating the printed color on the actual paper stock.
  
**The Reverse Pipeline & Gamut Checking (Lab to CMYK)**

When you input an Absolute L* a* b* target to check the gamut and generate a CMYK recipe:
1. **Inverse Scaling**: The engine takes your Absolute L* a* b* input and uses the wtpt tag to reverse-scale it back to a Media-Relative value.
2. **Gamut Mapping & GCR (B2A1)**: That relative value is fed into the B2A1 tag. Because the CMYK color gamut is significantly smaller than the visible L* a* b* spectrum, the B2A1 table dictates how out-of-gamut colors are compressed to the edges of the printable space. It also applies the profile's embedded Gray Component Replacement (GCR) or Under Color Removal (UCR) rules to determine the exact black ink separation.

**Why Roundtrips Don't Always Match ?**

Because the B2A1 table forces a specific GCR/black-generation rule during the L* a* b* $\rightarrow$ CMYK conversion, taking a CMYK value, converting it to L* a* b*, and converting it back to CMYK will often yield a slightly different CMYK recipe. 
