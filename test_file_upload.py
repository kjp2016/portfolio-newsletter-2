#!/usr/bin/env python3
"""
Simple test script to verify Streamlit file upload functionality.
"""

import streamlit as st
import pandas as pd
from io import BytesIO

def main():
    st.title("File Upload Test")
    
    st.write("This is a simple test to verify file upload functionality.")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=['csv', 'xlsx', 'xls', 'pdf', 'docx'],
        help="Test file upload"
    )
    
    if uploaded_file is not None:
        st.success(f"✅ File uploaded successfully!")
        st.write(f"**File name:** {uploaded_file.name}")
        st.write(f"**File size:** {uploaded_file.size} bytes")
        st.write(f"**File type:** {uploaded_file.type}")
        
        # Try to read the file
        try:
            if uploaded_file.type == "text/csv":
                df = pd.read_csv(uploaded_file)
                st.write("**CSV Content:**")
                st.dataframe(df.head())
            elif uploaded_file.type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                                      "application/vnd.ms-excel"]:
                df = pd.read_excel(uploaded_file)
                st.write("**Excel Content:**")
                st.dataframe(df.head())
            else:
                st.write(f"**File content type:** {uploaded_file.type}")
                st.write("File uploaded but content preview not available for this file type.")
                
        except Exception as e:
            st.error(f"Error reading file: {e}")
    else:
        st.info("📤 No file uploaded yet. Please select a file.")

if __name__ == "__main__":
    main() 