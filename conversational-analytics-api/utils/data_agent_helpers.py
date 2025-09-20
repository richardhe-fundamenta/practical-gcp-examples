from google.cloud import geminidataanalytics

PROJECT_ID = "rocketech-de-pgcp-sandbox"


def list_agents():
    # List data agents
    data_agent_client = geminidataanalytics.DataAgentServiceClient()
    request = geminidataanalytics.ListDataAgentsRequest(
        parent=f"projects/{PROJECT_ID}/locations/global",
    )

    # Make the request
    page_result = data_agent_client.list_data_agents(request=request)

    # Handle the response
    for response in page_result:
        print(response)


def get_agent(data_agent_id):
    # Get a data agent
    data_agent_client = geminidataanalytics.DataAgentServiceClient()
    request = geminidataanalytics.GetDataAgentRequest(
        name=f"projects/{PROJECT_ID}/locations/global/dataAgents/{data_agent_id}",
    )

    # Make the request
    response = data_agent_client.get_data_agent(request=request)

    # Handle the response
    print(response)


if __name__ == "__main__":
    # list_agents()
    get_agent(data_agent_id='ecommerce_analytics_data_agent')
