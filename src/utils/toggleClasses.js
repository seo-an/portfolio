export const addClassRemoveClass = ( parent, child, classNametag ) => {

	const len = parent.children.length;
	const decision = ((child.querySelector('input')) ? 'withCheckbox' : 'withoutCheckbox');

	switch (decision) {

		case 'withoutCheckbox':
			if (child.classList.contains(classNametag)) {
				child.classList.remove(classNametag);
				return;
			} else {
				for (let i = 0; i < len; i++) {
					if (parent.children[i].classList.contains(classNametag)) {
						parent.children[i].classList.remove(classNametag);
					}
				}
				child.classList.add(classNametag);
			}
			return child;

		case 'withCheckbox':
			if (child.classList.contains(classNametag)) {
				child.classList.remove(classNametag);
				child.querySelector('input').checked = false;
				return;
			} else {
				for (let i = 0; i < len; i++) {
					if (parent.children[i].classList.contains(classNametag)) {
						parent.children[i].classList.remove(classNametag);
						parent.children[i].querySelector('input').checked = false;
					}
				}
				child.classList.add(classNametag);
				child.querySelector('input').checked = true;
			}
			return child;
	}
	
};


export const addClassRemainClass = ( parent, child, classNametag ) => {

	const len = parent.children.length;

  for (let i = 0; i < len; i++) {
    if (parent.children[i].classList.contains(classNametag)) {
      parent.children[i].classList.remove(classNametag);
    }
  }
  child.classList.add(classNametag);

  return child;
};


export const simpleToggleClass = ( element, classNametag ) => {
	element.classList.toggle(classNametag);
}


// const clearClass = ( element, label ) => {
// 	// element = 클래스를 적용할 단위
// 	if (element.parentElement) {
// 		console.log('here');
// 		const parent = element.parentElement;
// 		for (let i = 0; i < parent.children.length; i++) {
// 			// console.log('huh', parent.children[i].classList.contains(label));
// 			if (parent.children[i].classList.contains(label)) {
// 				// console.log('here', i);
// 				// parent.children[i].classList.remove(label);
// 				parent.children[i].classList.toggle(label);
// 			}
// 		}
// 	} else {
// 		return;
// 	}
// }




	// if (child.classList.contains(classNametag)) {
	// 	child.classList.remove(classNametag);
	// 	child.querySelector('input').checked = false;
	// 	return;
	// } else {
	// 	for (let i = 0; i < len; i++) {
	// 		console.log('huh?', i);
	// 		if (parent.children[i].classList.contains(classNametag)) {
	// 			console.log('a', child.classList);
	// 			parent.children[i].classList.remove(classNametag);
	
	// 			if (parent.children[i].querySelector('input')) {
	// 				if (parent.children[i].querySelector('input').getAttribute('type') === 'checkbox') {
	// 					parent.children[i].querySelector('input').checked = false;
	// 				}
	// 			}
				
	// 		}
	// 	}
	// 	child.classList.add(classNametag);
	// 	child.querySelector('input').checked = true;
	// 	return child;
	// }