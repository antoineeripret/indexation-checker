#libraries used in the script
import streamlit as st
import pandas as pd
import requests
import json 

#Introduction 
st.title('Indexation checker')
st.markdown(
    '''Indexation checker done by [Antoine Eripret](https://twitter.com/antoineripret). You can report a bug or an issue in [Github](https://github.com/antoineeripret/indexation-checker).

You can check up to 15.000 URLs using a simple CSV file containing your URLs as an input. The script is based on https://www.valueserp.com/ and you need to have a paid account to unleash its full potential. 

**That being said, you can also sign up for a free account and check up to 125 URLs per month.**
''')

with st.expander('How does it work?'):
    st.markdown('''

    This tool leverages https://www.valueserp.com/ to check if you URL are indexed at scale, using their own dedicated infrastructure. The principle is simple: 
    - A search is launched using your URL as the keyword 
    - Top 20 results are extracted 
    - If your URL is not within the Top 20, the URL is marked as not indexed   
    
    ''')


#first step
with st.expander('STEP 1: Configure you extraction'):
    st.markdown('Please refer to [the playground](https://app.valueserp.com/playground) to know what the possible values are for these fields.')
    #inputs from user
    #api_key
    api_key = st.text_input('Enter your API Key')
    #country
    location = st.text_input('Country') 
    #Google domain 
    google_domain = st.text_input('Domain (google.fr, google.es...)') 

    #file upload
    st.header('File Upload')
    st.markdown(
        '''
        **Your CSV file must contain headers and be separated by commas.** Indicate below what is the name of the column containing your url list. 
        '''
    )

    uploaded_file = st.file_uploader("Choose a (comma-separated) CSV file.")
    if uploaded_file is not None:
        # Can be used wherever a "file-like" object is accepted:
        dataframe = pd.read_csv(uploaded_file)
        #colum selector
        column = st.selectbox('Choose the column with your URLs:', dataframe.columns)
        #calculate API cost to inform the user
        if st.button('Calulate API cost'):
            #remove duplicates and store it in session_state 
            st.session_state['urls'] = dataframe[column].unique()
            #batches cannot include more than 15k searches 
            if len(st.session_state['urls']) > 15000:
                st.write('You cannot check more than 15.000 URLs. Only the first 15.000 rows will be included.')
                urls = st.session_state['urls'][0:15000]
            else:
                urls = st.session_state['urls']
            st.write(f'The execution of the script will cost you {str(len(urls))} credits. ')

#second step
with st.expander('STEP 2: Launch searches'):
    st.markdown('**You cannot launch this part of the tool without completing step 1 first!! Execution will fail.**')
    if st.button('Launch process'):
        #create our list of sets of keywords
        keywords = []
        urls = st.session_state['urls']
        for i in range(0,len(urls),1000):
            keywords.append(urls[i:i+1000])
        
        param_list = []

        #create a list of parameters for each set
        for i in range(0, len(keywords)):
            params = []
            for i in range(0, len(keywords[i])):
                params.append({
                'api_key': api_key,
                'q': urls[i],
                'location': location,
                'google_domain': google_domain,
                'num': '20'
                    
                })
            param_list.append(params)
        
        #create our batch
        body = {
            "name": "indexation_checker",
            "enabled": True,
            "schedule_type": "manual",
            "priority": "normal",
            "searches_type":"web"
        }

        #send the instruction
        api_result = requests.post(f'https://api.valueserp.com/batches?api_key={api_key}', json=body)
        #get the results
        api_response = api_result.json()
        #get id 
        if api_response['request_info']['success']==True:
            st.session_state['batch_id']  = api_response['batch']['id']
            st.write('Batch successfully created!')
            st.write('Wait while your batch is being updated. It may take a while if you have a lot of searches!')
            batch_id = st.session_state['batch_id']

            for i in range(0, len(param_list)): 
                body = {"searches":[]}
                for param in param_list[i]:
                    body["searches"].append(param)

                api_result = requests.put(f'https://api.valueserp.com/batches/{batch_id}?api_key={api_key}', json=body).json()
                searches_count = api_result['batch']['searches_total_count']
            
            st.write(f'Number of searches successfully added: {str(searches_count)}')
                
        else:
            st.write('Error creating the bacth:')
            st.write(api_response)

#third step 
with st.expander('STEP 3: Run batch'):
    st.markdown('**You cannot launch this part of the tool without completing step 1 & 2 first!! Execution will fail.**')
    if st.button('Run batch'):
        batch_id = st.session_state['batch_id'] 
        api_result = requests.get(f'https://api.valueserp.com/batches/{batch_id}/start', params={'api_key':api_key})
        api_response = api_result.json()

        if api_response['request_info']['success'] == True:
            st.write('Batch successfully started. Exraction may take a while depending on the number of URLs you have.')
        else:
            st.write('Error starting the batch:')
            st.write(api_response)


with st.expander('STEP 4: Retrieve results'):
    st.markdown('Please visit your [batch dashboard](https://app.valueserp.com/batches) to retrieve your batch ID.')
    batch_id = st.text_input('Please indicate your batch ID')
    api_key = st.text_input('Enter your API key')
    
    if batch_id != '' and api_key!='':
        api_result = requests.get(f'https://api.valueserp.com/batches/{batch_id}/results/1/csv', params={'api_key':api_key})
        api_response = api_result.json()
        if 'Cannot retrieve' not in api_response:
            results = pd.DataFrame()
            for csv in api_response['result']['download_links']['pages']:
                results = pd.concat([results, pd.read_csv(csv)])
            
            indexation_results = pd.DataFrame(columns=['url','index_status'])

            for url in results['search.q'].unique():
                df = results[results['search.q']==url]
                if url in df['result.organic_results.link'].unique():
                    indexation_results.loc[len(indexation_results)] = [url,True]
                else:
                    indexation_results.loc[len(indexation_results)] = [url,False]
            
            data = indexation_results.groupby('index_status').agg({'url':'count'}).rename({'url':'count'}, axis=1)
            st.write('Indexation summary:')
            st.table(data)
            @st.cache
            def convert_df(df):
                return df.to_csv().encode('utf-8')


            csv = convert_df(indexation_results)

            st.download_button(
            "Press to download detail by url",
            csv,
            "file.csv",
            "text/csv",
            key='download-csv'
            )

        else:
            st.write('The batch hasn\'t finished to run yet. Please wait and run again!')
