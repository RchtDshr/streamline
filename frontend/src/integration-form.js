import { useState } from 'react';
import {
    Box,
    Autocomplete,
    TextField,
    Button,
    CircularProgress
} from '@mui/material';
import axios from 'axios';
import { AirtableIntegration } from './integrations/airtable';
import { NotionIntegration } from './integrations/notion';
import { DataForm } from './data-form';
import { HubspotIntegration } from './integrations/hubspot';

const integrationMapping = {
    'Notion': NotionIntegration,
    'Airtable': AirtableIntegration,
    'HubSpot': HubspotIntegration
};

const endpointMapping = {
    'Notion': 'notion',
    'Airtable': 'airtable',
    'HubSpot': 'hubspot'
};

export const IntegrationForm = () => {
    const [integrationParams, setIntegrationParams] = useState({});
    const [user, setUser] = useState('TestUser');
    const [org, setOrg] = useState('TestOrg');
    const [currType, setCurrType] = useState(null);
    const [isDisconnecting, setIsDisconnecting] = useState(false);
    
    const CurrIntegration = integrationMapping[currType];
    const isConnected = integrationParams?.credentials ? true : false;

    // Universal disconnect handler
    const handleDisconnect = async () => {
        if (!currType) return;
        
        try {
            setIsDisconnecting(true);
            const endpoint = endpointMapping[currType];
            const formData = new FormData();
            formData.append('user_id', user);
            formData.append('org_id', org);
            
            const response = await axios.post(`http://localhost:8000/integrations/${endpoint}/disconnect`, formData);
            
            if (response.status === 200) {
                // Clear integration parameters
                setIntegrationParams({});
                alert(`${currType} disconnected successfully`);
            }
        } catch (e) {
            alert(e?.response?.data?.detail || `Error disconnecting from ${currType}`);
        } finally {
            setIsDisconnecting(false);
        }
    };

    const handleTypeChange = (e, value) => {
        setCurrType(value);
        setIntegrationParams({});
    };

    return (
        <Box display='flex' justifyContent='center' alignItems='center' flexDirection='column' sx={{ width: '100%' }}>
            <Box display='flex' flexDirection='column'>
                <TextField
                    label="User"
                    value={user}
                    onChange={(e) => setUser(e.target.value)}
                    sx={{mt: 2}}
                />
                <TextField
                    label="Organization"
                    value={org}
                    onChange={(e) => setOrg(e.target.value)}
                    sx={{mt: 2}}
                />
                <Autocomplete
                    id="integration-type"
                    options={Object.keys(integrationMapping)}
                    sx={{ width: 300, mt: 2 }}
                    renderInput={(params) => <TextField {...params} label="Integration Type" />}
                    onChange={handleTypeChange}
                    value={currType}
                />
                
                {/* Universal Disconnect Button */}
                {currType && isConnected && (
                    <Button
                        variant='outlined'
                        color='error'
                        onClick={handleDisconnect}
                        disabled={isDisconnecting}
                        sx={{ mt: 2 }}
                    >
                        {isDisconnecting ? (
                            <CircularProgress size={20} />
                        ) : (
                            `Disconnect ${currType}`
                        )}
                    </Button>
                )}
            </Box>
            
            {currType && 
                <Box>
                    <CurrIntegration 
                        user={user} 
                        org={org} 
                        integrationParams={integrationParams} 
                        setIntegrationParams={setIntegrationParams} 
                    />
                </Box>
            }
            
            {integrationParams?.credentials && 
                <Box sx={{mt: 2}}>
                    <DataForm 
                        integrationType={integrationParams?.type} 
                        credentials={integrationParams?.credentials} 
                    />
                </Box>
            }
        </Box>
    );
}