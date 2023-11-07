import React from 'react';
import * as ReactDOMClient from 'react-dom/client';

import GlobalFonts from './styles/global/GlobalFonts';
import GlobalStyle from './styles/global/GlobalStyle';

import App from './App';


const root = ReactDOMClient.createRoot(document.getElementById('root'));
root.render(
  <>
    <GlobalFonts />
    <GlobalStyle />
    <App />
  </>
);