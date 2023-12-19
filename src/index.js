import React from 'react';
import * as ReactDOMClient from 'react-dom/client';

import GlobalFonts from './styles/global/GlobalFonts.js';
import GlobalStyle from './styles/global/GlobalStyle.js';

import App from './App.js';


const root = ReactDOMClient.createRoot(document.getElementById('root'));
root.render(
  <>
    <GlobalFonts />
    <GlobalStyle />
    <App />
  </>
);