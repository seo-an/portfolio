import { isThisString } from './detectDataType.js';
import { findAfterWordByRegEx } from './withRegExDoFindWord.js';
import { simpleToggleClass } from './toggleClasses.js';

// const 팝업세팅 = {
//   type: '', // window || modalLayer || modalWithButton
//   url: '/error', // window용
//   target: '_blank', // window용
//   features: 'width=200px, height=200px', // window용
//   location: 'center', // window용
//   toggleClassName: 'popped', // modal용
//   messageHTML: '<p>내용이 없습니다.</p>', // modal용
//   buttonText: '확인', // modal용
//   modalSubmitFunc: null, // modal용
// };

// 윈도우 팝업
const winPop = {
	type: 'window',
	url: null,
	target: null,
	features: null,
	location: null,
};

// 모달 팝업
const modal = {
	type: 'modalLayer',
	elements: null,
	toggleClassName: null,
	messageHTML: null,
	buttonText: null,
	modalSubmitFunc: null,
};

export const setPopup = ( parameters ) => {
	if (parameters.type === 'window') {
		winPop.url = isThisString(parameters.url) || '/error';
		winPop.target = isThisString(parameters.target) || '_blank';
		winPop.features = setWindowFeatures(parameters.features, parameters.location) || '';
	} else if (parameters.type === 'modalLayer') {

	}
	return;
};

// ---------------------------------------------------------------------------------
// Window
// 정렬을 위한 위치 정보 재설정
const rewriteString = ( str, position ) => {

	const widthRegex = /width=(\d+)/;
	const heightRegex = /height=(\d+)/;
	const leftRegex = /left=(\d+)/;
	const topRegex = /top=(\d+)/;

	const reg = {};
	const result = {};
	
	reg.widthVal = findAfterWordByRegEx(str, widthRegex);
	reg.heightVal = findAfterWordByRegEx(str, heightRegex);
	reg.leftVal = findAfterWordByRegEx(str, leftRegex);
	reg.topVal = findAfterWordByRegEx(str, topRegex);

	const defaultWidth = 700;
	const defaultHeight = 550;

	result.widthString = (reg.widthVal ? `width=${reg.widthVal}, ` : `width=${defaultWidth}px, `);
	result.heightString = (reg.heightVal ? `height=${reg.heightVal}, ` : `height=${defaultHeight}px, `);
	result.leftString = (reg.leftVal ? `left=${reg.leftVal}, ` : '');
	result.topString = (reg.topVal ? `top=${reg.topVal}, ` : '');

	if (position === 'center') {

		const _width = document.body.clientWidth;
		const _height = ((window.outerHeight < window.screen.availHeight) ? window.outerHeight : window.screen.availHeight);
		const _locationX = (!((window.screenX || window.screenLeft) < 0) ? (window.screenX || window.screenLeft) : 0);
		
		const horizontal = (reg.widthVal ? (_locationX + ((_width / 2) - (reg.widthVal / 2))) : (_locationX + ((_width / 2) - (reg.widthVal / 2))));
		const vertical = (reg.heightVal ? ((_height / 2) - (reg.heightVal / 2)) : ((defaultHeight / 2) - (reg.heightVal / 2)));

		result.leftString = (reg.leftVal ? `left=${horizontal}` : '');
		result.topString = (reg.topVal ? `top=${vertical}` : '');

		return result;
	};

	return result;

};

const setWindowFeatures = ( str, position ) => {
	const result = rewriteString(str, position);
	return `${result.widthString} ${result.heightString} ${result.leftString} ${result.topString} noopener noreferrer`;
};

const winPopped = ( url, target, windowFeatures ) => {
	window.open(url, target, windowFeatures);
	return;
};

// submit function 받을 준비
export const windowPopup = ( func ) => {
	winPopped(winPop.url, winPop.target, winPop.features);
};



// ---------------------------------------------------------------------------------
// Modal

// export const getPopupElementsAndCustomCssName = ( cssClass ) => {
// 	return modal.cssName = cssClass;
// };

// export const getPopupCoreMessage = ( html ) => {
// 	return modal.message = html;
// };

const setMessage = ( parameters ) => {
	const messageWrapper = (parameters.elements.children[0].classList.contains('modal-body')) ? parameters.elements.children[0] : parameters.elements;

	if (messageWrapper.classList.contains('modal-core') === true) {
		messageWrapper.innerHTML = parameters.messageHTML;
	} else if (messageWrapper.children[0].classList.contains('modal-core') === true) {
		messageWrapper.children[0].innerHTML = parameters.messageHTML;
	}
};

const createModalExitButton = ( parent, toggleClassName, text, func ) => {
	let upbringing = null;
	const standard = parent;

	if (parent.children[0].classList.contains('modal-body')) {
		upbringing = parent.children[0];
	} else {
		upbringing = parent;
	}

	const modalExitButtonWrap = document.createElement('div');
	modalExitButtonWrap.classList.add('modal-button');
	const MODAL_TOGGLE_CSS_CLASS_NAME = (isThisString(toggleClassName) ? toggleClassName : 'popped');
	const BUTTON_TEXT = (isThisString(text) ? text : '확인');

	const clickEvent = (event) => {
		simpleToggleClass(standard, MODAL_TOGGLE_CSS_CLASS_NAME);
		document.body.removeChild(standard);

		event.target.removeEventListener('click', (event) => clickEvent(event));
	};

	const button = document.createElement('button');
	button.type = 'submit';
	button.textContent = BUTTON_TEXT;

	button.addEventListener('click', (event) => {
		// event.preventDefault();
		
		if (!(func === null)) {
			// const onSubmit = async (event) => await func(event);
			// const trigger = onSubmit(event);
			// console.log('trigger', trigger);
			// return (!(trigger === false)) ? clickEvent(event) : null;
			func(event);
		} else {
			clickEvent(event);
		}
	});

	upbringing.appendChild(modalExitButtonWrap);
	modalExitButtonWrap.appendChild(button);
	
	return;
};


export const modalPopupAllowClickOuterSpace = ( parameters ) => {
	const modalBackground = document.createElement('div');
	modalBackground.style.height = (document.body.clientHeight < window.innerHeight) ? `${window.innerHeight}px` : `${document.body.clientHeight}px`;

	const modalBody = document.createElement('div');
	const modalCore = document.createElement('div');

	const MODAL_BACKGROUND_CSS_CLASS_NAME = 'modal-background';
	const MODAL_BODY_CSS_CLASS_NAME = 'modal-body';
	const MODAL_CORE_CSS_CLASS_NAME = 'modal-core';
	const MODAL_TOGGLE_CSS_CLASS_NAME = parameters.toggleClassName || 'popped';

	modalBackground.classList.add(MODAL_BACKGROUND_CSS_CLASS_NAME);
	modalBody.classList.add(MODAL_BODY_CSS_CLASS_NAME);
	modalCore.classList.add(MODAL_CORE_CSS_CLASS_NAME);

	const clickEvent = (event) => {
		if (event.target.classList.contains(MODAL_BODY_CSS_CLASS_NAME)) {
			simpleToggleClass(modalBackground, MODAL_TOGGLE_CSS_CLASS_NAME);
			document.body.removeChild(modalBackground);
		}
	};

	document.body.appendChild(modalBackground);
	modalBackground.appendChild(modalBody);
	modalBody.appendChild(modalCore);

	simpleToggleClass(modalBackground, MODAL_TOGGLE_CSS_CLASS_NAME);

	modalBackground.addEventListener('click', (event) => clickEvent(event));
	
	modal.elements = modalBackground;

	setMessage(modal);

	modalBackground.removeEventListener('click', (event) => clickEvent(event));

	return;
};



export const modalPopupDisallowClickOuterSpace = ( parameters ) => {
	const modalBackground = document.createElement('div');
	modalBackground.style.height = (document.body.clientHeight < window.innerHeight) ? `${window.innerHeight}px` : `${document.body.clientHeight}px`;

	const modalBody = document.createElement('div');
	const modalCore = document.createElement('div');

	const MODAL_BACKGROUND_CSS_CLASS_NAME = 'modal-background';
	const MODAL_BODY_CSS_CLASS_NAME = 'modal-body';
	const MODAL_CORE_CSS_CLASS_NAME = 'modal-core';
	const MODAL_TOGGLE_CSS_CLASS_NAME = parameters.toggleClassName || 'popped';

	const MODAL_BUTTON_TEXT = parameters.buttonText || '확인';

	modalBackground.classList.add(MODAL_BACKGROUND_CSS_CLASS_NAME);
	modalBody.classList.add(MODAL_BODY_CSS_CLASS_NAME);
	modalCore.classList.add(MODAL_CORE_CSS_CLASS_NAME);

	document.body.appendChild(modalBackground);
	modalBackground.appendChild(modalBody);
	modalBody.appendChild(modalCore);

	simpleToggleClass(modalBackground, MODAL_TOGGLE_CSS_CLASS_NAME);

	if (modalBackground.classList.contains(MODAL_TOGGLE_CSS_CLASS_NAME)) {
		createModalExitButton(modalBackground, MODAL_TOGGLE_CSS_CLASS_NAME, MODAL_BUTTON_TEXT, parameters.modalSubmitFunc);
	}
	
	const reloadPage = (event) => {
		// console.log('huh', event.key, event.code, event.which);
		if (event.key === 'Escape' || event.code === 'Escape' || event.which === 27 || event.keyCode === 27) {
			// simpleToggleClass(modalBackground, MODAL_TOGGLE_CSS_CLASS_NAME);
			event.preventDefault();
			window.location.reload();
		}
	};

	document.addEventListener('keydown', (e) => reloadPage(e));

	modal.elements = modalBackground;

	setMessage(modal);

	document.removeEventListener('keydown', (e) => reloadPage(e));

	return;
};


// submit function 받을 준비
export const modalPopup = ( parameters ) => {
	// console.log('모달팝업 안에있어', parameters);
	modal.type = parameters.type;
	modal.toggleClassName = parameters.toggleClassName || 'popped';
	modal.messageHTML = parameters.messageHTML;
	modal.buttonText = parameters.buttonText;
	modal.modalSubmitFunc = parameters.modalSubmitFunc || null;

	switch (modal.type) {
		case ('modalLayer'):
			// console.log('레이어 모달');
			modalPopupAllowClickOuterSpace(modal);
			break;
		case ('modalWithButton'):
			// console.log('버튼 모달');
			modalPopupDisallowClickOuterSpace(modal);
			break;
		default:
			console.error('해당하는 modal이 없습니다.');
			break;
	}
};