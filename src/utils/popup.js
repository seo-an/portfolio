import { isThisString } from "./detectDataType";
import { findByRegEx } from "./withRegExDoThis";
import { simpleToggleClass } from "./toggleClasses";

// 윈도우 팝업
const winPop = {
	url: '',
	target: '',
	features: '',
};

const rewriteString = ( str, position ) => {

	const widthRegex = /width=(\d+)/;
	const heightRegex = /height=(\d+)/;
	const leftRegex = /left=(\d+)/;
	const topRegex = /top=(\d+)/;

	const reg = {};
	const result = {};
	
	reg.widthVal = findByRegEx(str, widthRegex);
	reg.heightVal = findByRegEx(str, heightRegex);
	reg.leftVal = findByRegEx(str, leftRegex);
	reg.topVal = findByRegEx(str, topRegex);

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

const popped = ( url, target, windowFeatures ) => {
	window.open(url, target, windowFeatures);
	return;
};

export const getPopupPageInfo = ( parameters ) => {

	winPop.url = isThisString(parameters.url) || '/error';
	winPop.target = isThisString(parameters.target) || '_blank';
	winPop.features = setWindowFeatures(parameters.features, parameters.location) || '';
	
	return;

};

export const windowPopup = () => {
	popped(winPop.url, winPop.target, winPop.features);
};


// 모달 팝업
const modal = {
	elements: '',
	cssName: '',
	message: '',
};

export const getPopupElementsAndCustomCssName = ( cssClass ) => {
	return modal.cssName = cssClass;
};

export const getPopupCoreMessage = ( html ) => {
	return modal.message = html;
};

const setMessage = ( ingredients ) => {
	const messageWrapper = (ingredients.elements).children[0];

	if (messageWrapper.classList.contains('modal-core') === true) {
		messageWrapper.innerHTML = ingredients.message;
	}
};

const createModalExitButton = ( parent, className, text ) => {
	const modalExitButtonWrap = document.createElement('div');
	modalExitButtonWrap.classList.add('button-wrap'); // 나중에 css 추가
	const MODAL_TOGGLE_CSS_CLASS_NAME = (isThisString(className) ? className : 'popped');
	const BUTTON_TEXT = (isThisString(text) ? text : '확인');

	const clickEvent = (event) => {
		simpleToggleClass(parent, MODAL_TOGGLE_CSS_CLASS_NAME);
		document.body.removeChild(parent);

		event.target.removeEventListener('click', (event) => clickEvent(event));
	};

	const button = document.createElement('button');
	button.textContent = BUTTON_TEXT;
	button.addEventListener('click', (event) => {
		clickEvent(event);
	});

	parent.appendChild(modalExitButtonWrap);
	modalExitButtonWrap.appendChild(button);
	
	return;
};



export const modalPopupAllowClickOuterSpace = () => {

	const modalBody = document.createElement('div');
	const modalCore = document.createElement('div');

	const MODAL_BODY_CSS_CLASS_NAME = 'modal-body';
	const MODAL_CORE_CSS_CLASS_NAME = 'modal-core';
	const MODAL_TOGGLE_CSS_CLASS_NAME = 'popped';

	modalBody.classList.add(MODAL_BODY_CSS_CLASS_NAME);
	modalCore.classList.add(MODAL_CORE_CSS_CLASS_NAME);

	const clickEvent = (event) => {
		if (event.target.classList.contains(MODAL_BODY_CSS_CLASS_NAME)) {
			simpleToggleClass(modalBody, MODAL_TOGGLE_CSS_CLASS_NAME);
			document.body.removeChild(modalBody);
		}
	};

	document.body.appendChild(modalBody);
	modalBody.appendChild(modalCore);

	simpleToggleClass(modalBody, MODAL_TOGGLE_CSS_CLASS_NAME);
	
	modalBody.addEventListener('click', (event) => clickEvent(event));
	
	modal.elements = modalBody;

	setMessage(modal);

	modalBody.removeEventListener('click', (event) => clickEvent(event));

	return;
};


export const modalPopupDisallowClickOuterSpace = () => {
	const modalBody = document.createElement('div');
	const modalCore = document.createElement('div');
	
	const MODAL_BODY_CSS_CLASS_NAME = 'modal-body';
	const MODAL_CORE_CSS_CLASS_NAME = 'modal-core';
	const MODAL_TOGGLE_CSS_CLASS_NAME = 'popped';

	modalBody.classList.add(MODAL_BODY_CSS_CLASS_NAME);
	modalCore.classList.add(MODAL_CORE_CSS_CLASS_NAME);

	document.body.appendChild(modalBody);
	modalBody.appendChild(modalCore);

	simpleToggleClass(modalBody, MODAL_TOGGLE_CSS_CLASS_NAME);

	if (modalBody.classList.contains(MODAL_TOGGLE_CSS_CLASS_NAME)) {
		createModalExitButton(modalBody, MODAL_TOGGLE_CSS_CLASS_NAME, '응답하라');
	}
	
	modal.elements = modalBody;

	setMessage(modal);

	return;
};