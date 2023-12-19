// import { useState } from 'react';
import { setPopup, windowPopup } from '../../../utils/popup.js';

export const WindowPopupExamplePageView = () => {

	const argument = {
		type: 'window',
		url: '/popup-view',
		target: '_blank',
		features: 'width=500px, height=500px, left=20px, top=200px',
		location: 'center'
	}

	setPopup( argument );

	return (
		<>
			<div>
				<h1>Window 팝업</h1>
			</div>

			<button onClick={windowPopup}>윈도우 팝업</button>
		</>
	)
};