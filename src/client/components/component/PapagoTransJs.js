import { useState } from 'react';

import { getValue } from '../../action/actionsForRestApi.js';

import { PapagoTransForm } from '../../view/pages/PapagoTransForm.js';
import { PapagoTransDisplay } from '../../view/pages/PapagoTransDisplay.js';


export const PapagoTransJS = () => {
	const [original, setOriginal] = useState(null);
	const [translated, setTranslated] = useState(null);

	const postPapago = async ( event ) => {
		event.preventDefault();
	
		const URL_TO_NODE = '/api/papago';
		const inputStr = getValue('papago');
		setOriginal(inputStr);
	
		const data = {
			source: 'ko',
			target: 'en',
			text: inputStr
		};
	
		try {
			const response = await fetch(URL_TO_NODE, {
				method: "POST",
				headers: {
					"Content-Type": "application/json"
				},
				body: JSON.stringify(data)
			}).then(res => {
				if (!res.ok) {
					throw new Error('HTTP POST ERROR :: status ', response.status);
				}
				return res.json(); // json 반환
			}).then(data => {
				return JSON.parse(data.responses); // 객체로 변환
			});
	
			return setTranslated(response.message.result.translatedText);
	
		} catch (error) {
			return console.error('CAN NOT TRY TO FETCH :: ', error);
		}
		
	};

	return (
		<>
			<PapagoTransForm props = {postPapago} />
			<PapagoTransDisplay original = {original} translated = {translated}/>
		</>
	);
}