# 💊 MediSate AI

## Medicine Information & Interaction Screening Assistant

MediSate AI is a Streamlit-based application that retrieves
medicine information from healthcare databases and screens
multiple medicines for potential interactions.

The application is designed for **educational and informational
purposes only** and does not replace professional medical advice.

## 🌐 Live Demo

🚀 **Try MediSate AI:**  
https://medisate-ai-evm4jk2k8lvfjv9udjmt2e.streamlit.app/

## 🎯 Problem Statement

Finding reliable medicine information and checking whether
multiple medicines may have potential interactions can be
difficult for users.

MediSate AI provides a simple web interface where users can
enter medicine names and receive information retrieved from
external healthcare databases.

## ✨ Features

- 💊 Enter one or more medicine names
- 🔎 Identify medicines using RxNorm
- 📋 Retrieve official drug-label information
- 🧾 Display medicine uses and important warnings
- 🔄 Support different dosage forms
- ⚠️ Screen for potential medicine interactions
- 🤖 Optional AI-assisted summarization
- 🛡️ Avoid generating unsupported medicine information
- 🌐 Accessible through a web browser
- 🚀 Deployed using Streamlit Community Cloud

## 🧠 How It Works

```text
User enters medicine
        ↓
RxNorm medicine identification
        ↓
Retrieve official drug-label information
        ↓
Verify retrieved information
        ↓
Extract relevant medicine information
        ↓
Check potential interactions
        ↓
Display results in Streamlit
