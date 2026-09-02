import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Clinic No-Show Analytics", layout="wide", page_icon="")
st.title("🏥 Clinic Appointment No-Show Analytics Dashboard")

# --- DATA LOADING & PREPROCESSING ---
@st.cache_data
def load_and_process_data():
    """Loads Excel/CSV and performs essential preprocessing."""

    file_path = r"D:\Internship\clinic_appointment.csv.xlsx"

    if not os.path.exists(file_path):
        st.error(f"❌ File '{file_path}' not found! Please place it in the same folder.")
        return None

    try:
        df = pd.read_excel(file_path)

    except Exception:
        try:
            df = pd.read_csv(file_path.replace('.xlsx', '.csv'))

        except Exception:
            st.error("❌ Could not read file. Ensure it is a valid Excel or CSV.")
            return None

    # Essential Preprocessing Pipeline
    df['ScheduledDay'] = pd.to_datetime(df['ScheduledDay'])
    df['AppointmentDay'] = pd.to_datetime(df['AppointmentDay'], errors='coerce')
    
    # Calculate Lead Time (days between scheduling and appointment)
    df['LeadTime_Days'] = (df['AppointmentDay'] - df['ScheduledDay']).dt.days
    
    # Clean No-show column (handle Yes/No/yes/no variations)
    df['No-Show'] = df['No-show'].astype(str).str.strip().str.lower().map({'yes': True, 'no': False})
    df['No-Show'] = df['No-Show'].fillna(False)
    df['No_Show'] = df['No-Show']
    # Fix negative lead times (data errors where appointment was before scheduling)
    df.loc[df['LeadTime_Days'] < 0, 'LeadTime_Days'] = 0
    
    # Create Age Groups for demographic analysis
    bins = [0, 18, 35, 50, 65, 120]
    labels = ['0-18', '19-35', '36-50', '51-65', '65+']
    df['Age_Group'] = pd.cut(df['Age'], bins=bins, labels=labels, right=True)
    
    # Extract Day of Week for temporal analysis
    df['Day_of_Week'] = df['AppointmentDay'].dt.day_name()
    
    return df

df = load_and_process_data()

if df is None:
    st.stop()

# --- SIDEBAR FILTERS (Essential Interactive Buttons) ---
st.sidebar.header(" Filters")

date_range = st.sidebar.date_input(
    "Appointment Date Range",
    value=(df['AppointmentDay'].min(), df['AppointmentDay'].max()),
    min_value=df['AppointmentDay'].min(),
    max_value=df['AppointmentDay'].max()
)

selected_neighborhoods = st.sidebar.multiselect(
    "Neighbourhood", 
    options=sorted(df['Neighbourhood'].unique()),
    default=[]
)

selected_gender = st.sidebar.multiselect(
    "Gender", 
    options=sorted(df['Gender'].unique()),
    default=[]
)

sms_filter = st.sidebar.radio("SMS Reminder Status", ["All", "Received SMS", "No SMS"])

health_conditions = st.sidebar.multiselect(
    "Health Conditions", 
    options=['Hypertension', 'Diabetes', 'Alcoholism', 'Handcap'],
    default=[]
)

# --- APPLY FILTERS TO DATAFRAME ---
df['AppointmentDay'] = pd.to_datetime(
    df['AppointmentDay'],
    errors='coerce'
)

filtered_df = df.copy()

filtered_df = filtered_df[
    (filtered_df['AppointmentDay'].dt.date >= date_range[0]) &
    (filtered_df['AppointmentDay'].dt.date <= date_range[1])
]

if selected_neighborhoods:
    filtered_df = filtered_df[filtered_df['Neighbourhood'].isin(selected_neighborhoods)]
if selected_gender:
    filtered_df = filtered_df[filtered_df['Gender'].isin(selected_gender)]
if sms_filter == "Received SMS":
    filtered_df = filtered_df[filtered_df['SMS_received'] == 1]
elif sms_filter == "No SMS":
    filtered_df = filtered_df[filtered_df['SMS_received'] == 0]

# Health condition filtering logic
for cond in health_conditions:
    col_map = {'Hypertension': 'Hipertension', 'Diabetes': 'Diabetes', 
               'Alcoholism': 'Alcoholism', 'Handcap': 'Handcap'}
    filtered_df = filtered_df[filtered_df[col_map[cond]] == 1]

# --- KPI CARDS ROW ---
total_appts = len(filtered_df)
no_show_rate = (filtered_df['No_Show'].sum() / total_appts * 100) if total_appts > 0 else 0
sms_sent = filtered_df['SMS_received'].sum()
avg_lead = filtered_df['LeadTime_Days'].mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Appointments", f"{total_appts:,}")
col2.metric("No-Show Rate", f"{no_show_rate:.1f}%")
col3.metric("SMS Sent", f"{sms_sent:,}")
col4.metric("Avg Lead Time", f"{avg_lead:.1f} days")

st.divider()

# --- CHARTS GRID ---
row1_col1, row1_col2 = st.columns([2, 1])

with row1_col1:
    st.subheader("📈 Monthly No-Show Trend")
    trend = filtered_df.groupby(filtered_df['AppointmentDay'].dt.to_period('M')).agg(
        Total=('AppointmentID', 'count'),
        No_Shows=('No-Show', 'sum')
    ).reset_index()
    trend['Month'] = trend['AppointmentDay'].astype(str)
    trend['No-Show %'] = (trend['No_Shows'] / trend['Total'] * 100).round(1)
    
    fig_trend = px.line(trend, x='Month', y='No-Show %', markers=True, 
                        title="Monthly No-Show Rate (%)", template="plotly_white")
    fig_trend.update_traces(line=dict(color='#2563eb', width=3), marker=dict(size=8))
    st.plotly_chart(fig_trend, width='stretch')

with row1_col2:
    st.subheader("👤 Demographics by Age Group")
    demo_fig = px.bar(
        filtered_df.groupby(['Age_Group', 'No_Show']).size().reset_index(name='Count'),
        x='Age_Group', y='Count', color='No_Show', barmode='group',
        color_discrete_map={True: '#ef4444', False: '#22c55e'},
        title="Appointments vs No-Shows"
    )
    st.plotly_chart(demo_fig, width='stretch')

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.subheader(" Top 10 Neighbourhoods by No-Show Rate")
    top_nbh = filtered_df.groupby('Neighbourhood').agg(
        Total=('AppointmentID', 'count'),
        No_Shows=('No_Show', 'sum')
    ).reset_index()
    top_nbh['Rate'] = (top_nbh['No_Shows'] / top_nbh['Total'] * 100).round(1)
    top_nbh = top_nbh.nlargest(10, 'Rate')
    
    fig_nbh = px.bar(top_nbh, x='Rate', y='Neighbourhood', orientation='h',
                     color='Rate', color_continuous_scale='RdYlGn_r',
                     text='Rate', title="Highest Risk Areas")
    fig_nbh.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_nbh,width='stretch')

with row2_col2:
    st.subheader("💬 SMS Reminder Effectiveness")
    sms_data = filtered_df.groupby('SMS_received').agg(
        Total=('AppointmentID', 'count'),
        No_Shows=('No_Show', 'sum')
    ).reset_index()
    sms_data['Label'] = sms_data['SMS_received'].map({0: 'No SMS', 1: 'Received SMS'})
    sms_data['Show'] = sms_data['Total'] - sms_data['No_Shows']
    
    fig_sms = go.Figure(data=[
        go.Bar(name='Showed Up', x=sms_data['Label'], y=sms_data['Show'], marker_color='#22c55e'),
        go.Bar(name='No-Show', x=sms_data['Label'], y=sms_data['No_Shows'], marker_color='#ef4444')
    ])
    fig_sms.update_layout(barmode='stack', title="Attendance vs SMS Status", template="plotly_white")
    st.plotly_chart(fig_sms, width='stretch')

# --- FOOTER ---
st.divider()
st.caption("Dashboard powered by Streamlit & Plotly | Data Source: KaggleV2-May-2016")