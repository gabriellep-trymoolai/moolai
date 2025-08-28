import { PublicClientApplication, type Configuration } from 
"@azure/msal-browser";

// 🔹 Real values
const TENANT = "moolaib2c.onmicrosoft.com";
const POLICY = "B2C_1_susi";
const SPA_CLIENT_ID = "ac41a9da-ca72-48a3-a468-d9db5b218c4d";     
// frontend app
const API_CLIENT_ID = "0263d89f-754d-4861-a401-8a44a0611618";     
// backend API app

// Scope string uses the Application ID URI with scope name
export const apiScopes = 
[`api://${API_CLIENT_ID}/access_as_user`];

const config: Configuration = {
  auth: {
    clientId: SPA_CLIENT_ID,
    authority: 
`https://${TENANT}.b2clogin.com/${TENANT}/${POLICY}/v2.0`,
    knownAuthorities: [`${TENANT}.b2clogin.com`],
    redirectUri: "http://localhost:3000/verify-email",
    postLogoutRedirectUri: "http://localhost:3000",
  },
  cache: {
    cacheLocation: "localStorage",
    storeAuthStateInCookie: false,
  },
};

export const msal = new PublicClientApplication(config);


