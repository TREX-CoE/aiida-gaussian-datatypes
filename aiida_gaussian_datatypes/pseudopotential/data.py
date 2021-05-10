# -*- coding: utf-8 -*-
# Copyright (c), Tiziano Müller
# SPDX-License-Identifier: MIT

"""
Gaussian Pseudopotential Data class
"""

from aiida.orm import Data, Group

from .utils import write_cp2k_pseudo, cp2k_pseudo_file_iter


class Pseudopotential(Data):
    """
    Gaussian Pseudopotential (gpp) class to store gpp's in database and retrieve them.
    fixme: extend to NLCC pseudos.
    """

    def __init__(
        self,
        element=None,
        name=None,
        aliases=None,
        tags=None,
        n_el=None,
        local=None,
        non_local=None,
        version=1,
        **kwargs,
    ):
        """
        :param element: string containing the name of the element
        :param name: identifier for this basis set, usually something like <name>-<size>[-q<nvalence>]
        :param aliases: alternative names
        :param tags: additional tags
        :param n_el: number of valence electrons covered by this basis set
        :param local: see :py:attr:`~local`
        :param local: see :py:attr:`~non_local`
        """

        if not aliases:
            aliases = []

        if not tags:
            tags = []

        if not n_el:
            n_el = []

        if not non_local:
            non_local = []

        if "label" not in kwargs:
            kwargs["label"] = name

        super(Pseudopotential, self).__init__(**kwargs)

        self.set_attribute("name", name)
        self.set_attribute("element", element)
        self.set_attribute("tags", tags)
        self.set_attribute("aliases", aliases)
        self.set_attribute("n_el", n_el)
        self.set_attribute("local", local)
        self.set_attribute("non_local", non_local)
        self.set_attribute("version", version)

    def store(self, *args, **kwargs):
        """
        Store the node, ensuring that the combination (element,name,version) is unique.
        """
        # TODO: this uniqueness check is not race-condition free.

        from aiida.common.exceptions import UniquenessError, NotExistent

        try:
            existing = self.get(self.element, self.name, self.version, match_aliases=False)
        except NotExistent:
            pass
        else:
            raise UniquenessError(
                f"Gaussian Pseudopotential already exists for"
                f" element={self.element}, name={self.name}, version={self.version}: {existing.uuid}"
            )

        return super(Pseudopotential, self).store(*args, **kwargs)

    def _validate(self):
        super(Pseudopotential, self)._validate()

        from pydantic import BaseModel, ValidationError as PydanticValidationError
        from typing import List, Optional
        from aiida.common.exceptions import ValidationError

        class PseudoDataLocal(BaseModel):
            r: float
            coeffs: List[float]

            class Config:
                validate_all = True
                extra = "forbid"

        class PseudoDataNonLocal(BaseModel):
            r: float
            nproj: int
            coeffs: List[float]

            class Config:
                validate_all = True
                extra = "forbid"

        class PseudoData(BaseModel):
            name: str
            element: str
            tags: List[str]
            aliases: List[str]
            n_el: Optional[List[int]] = None
            local: PseudoDataLocal
            non_local: List[PseudoDataNonLocal]
            version: int

            class Config:
                validate_all = True
                extra = "forbid"

        try:
            PseudoData.parse_obj(self.attributes)
        except PydanticValidationError as exc:
            raise ValidationError(str(exc))

        for nlocal in self.attributes["non_local"]:
            if len(nlocal["coeffs"]) != nlocal["nproj"] * (nlocal["nproj"] + 1) // 2:
                raise ValidationError("invalid number of coefficients for non-local projection")

    @property
    def element(self):
        """
        the atomic kind/element this pseudopotential is for

        :rtype: str
        """
        return self.get_attribute("element", None)

    @property
    def name(self):
        """
        the name for this pseudopotential

        :rtype: str
        """
        return self.get_attribute("name", None)

    @property
    def aliases(self):
        """
        a list of alternative names

        :rtype: []
        """
        return self.get_attribute("aliases", [])

    @property
    def tags(self):
        """
        a list of tags

        :rtype: []
        """
        return self.get_attribute("tags", [])

    @property
    def version(self):
        """
        the version of this pseudopotential

        :rtype: int
        """
        return self.get_attribute("version", None)

    @property
    def n_el(self):
        """
        Return the number of electrons per angular momentum
        :rtype:list
        """

        return self.get_attribute("n_el", [])

    @property
    def local(self):
        """
        Return the local part

        The format of the returned dictionary::

            {
                'r': float,
                'coeffs': [float, float, ...],
            }

        :rtype:dict
        """
        return self.get_attribute("local", None)

    @property
    def non_local(self):
        """
        Return a list of non-local projectors (for l=0,1...).

        Each list element will have the following format::

            {
                'r': float,
                'nprj': int,
                'coeffs': [float, float, ...],  # only the upper-triangular elements
            }

        :rtype:list
        """
        return self.get_attribute("non_local", [])

    @classmethod
    def get(cls, element, name=None, version="latest", match_aliases=True, group_label=None):
        """
        Get the first matching Pseudopotential for the given parameters.

        :param element: The atomic symbol
        :param name: The name of the pseudo
        :param version: A specific version (if more than one in the database and not the highest/latest)
        :param match_aliases: Whether to look in the list of of aliases for a matching name
        """
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.common.exceptions import NotExistent, MultipleObjectsError

        query = QueryBuilder()

        params = {}

        if group_label:
            query.append(Group, filters={"label": group_label}, tag="group")
            params["with_group"] = "group"

        query.append(Pseudopotential, **params)

        filters = {"attributes.element": {"==": element}}

        if version != "latest":
            filters["attributes.version"] = {"==": version}

        if name:
            if match_aliases:
                filters["attributes.aliases"] = {"contains": [name]}
            else:
                filters["attributes.name"] = {"==": name}

        query.add_filter(Pseudopotential, filters)

        # SQLA ORM only solution:
        # query.order_by({Pseudopotential: [{"attributes.version": {"cast": "i", "order": "desc"}}]})
        # items = query.first()

        items = sorted(query.iterall(), key=lambda p: p[0].version, reverse=True)

        if not items:
            raise NotExistent(
                f"No Gaussian Pseudopotential found for element={element}, name={name}, version={version}"
            )

        # if we get different names there is no well ordering, sorting by version only works if they have the same name
        if len(set(p[0].name for p in items)) > 1:
            raise MultipleObjectsError(
                f"Multiple Gaussian Pseudopotentials found for element={element}, name={name}, version={version}"
            )

        return items[0][0]

    @classmethod
    def from_cp2k(cls, fhandle, filters=None, duplicate_handling="ignore", ignore_invalid=False):
        """
        Constructs a list with pseudopotential objects from a Pseudopotential in CP2K format

        :param fhandle: open file handle
        :param filters: a dict with attribute filter functions
        :param duplicate_handling: how to handle duplicates ("ignore", "error", "new" (version))
        :param ignore_invalid: whether to ignore invalid entries silently
        :rtype: list
        """

        from aiida.common.exceptions import UniquenessError, NotExistent

        if not filters:
            filters = {}

        def matches_criteria(pseudo):
            return all(fspec(pseudo[field]) for field, fspec in filters.items())

        def exists(pseudo):
            try:
                cls.get(pseudo["element"], pseudo["name"], match_aliases=False)
            except NotExistent:
                return False

            return True

        pseudos = [p for p in cp2k_pseudo_file_iter(fhandle, ignore_invalid) if matches_criteria(p)]

        if duplicate_handling == "ignore":  # simply filter duplicates
            pseudos = [p for p in pseudos if not exists(p)]

        elif duplicate_handling == "error":
            for pseudo in pseudos:
                try:
                    latest = cls.get(pseudo["element"], pseudo["name"], match_aliases=False)
                except NotExistent:
                    pass
                else:
                    raise UniquenessError(
                        f"Gaussian Pseudopotential already exists for"
                        f" element={pseudo['element']}, name={pseudo['name']}: {latest.uuid}"
                    )

        elif duplicate_handling == "new":
            for pseudo in pseudos:
                try:
                    latest = cls.get(pseudo["element"], pseudo["name"], match_aliases=False)
                except NotExistent:
                    pass
                else:
                    pseudo["version"] = latest.version + 1

        else:
            raise ValueError(f"Specified duplicate handling strategy not recognized: '{duplicate_handling}'")

        return [cls(**p) for p in pseudos]

    def to_cp2k(self, fhandle):
        """
        Write this Pseudopotential instance to a file in CP2K format.

        :param fhandle: open file handle
        """
        write_cp2k_pseudo(
            fhandle,
            self.element,
            self.name,
            self.n_el,
            self.local,
            self.non_local,
            comment=f"from AiiDA Pseudopotential<uuid: {self.uuid}>",
        )
