"""
Attio CRM API client for creating and managing objects.
Supports creating: people, companies, deals, and users.
Intelligently determines object type from natural language input.
"""

import logging
from typing import Dict, Optional, Any
import re

import requests
import google.generativeai as genai

from config import Config
from gemini_processor import LeadData

logger = logging.getLogger(__name__)

# Configure Gemini for web searches
genai.configure(api_key=Config.GOOGLE_API_KEY)


class AttioAPIError(Exception):
    """Raised when Attio API operations fail."""
    pass


class AttioClient:
    """Client for interacting with Attio CRM API."""

    def __init__(self):
        """Initialize Attio client with API credentials."""
        if not Config.ATTIO_API_KEY:
            raise AttioAPIError("ATTIO_API_KEY not configured")

        self.api_key = Config.ATTIO_API_KEY
        self.base_url = Config.ATTIO_API_URL

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_record(
        self,
        lead_data: LeadData
    ) -> Dict[str, Any]:
        """
        Create a new record in Attio (person, company, deal, or user).

        Automatically determines the correct object type and endpoint
        based on lead_data.object_type. If a field doesn't exist, it will
        be automatically created.

        For people with companies, this will:
        1. Create the company record first
        2. Link the person to the company

        Args:
            lead_data: Structured lead data from Gemini

        Returns:
            Dictionary containing created record information

        Raises:
            AttioAPIError: If record creation fails
        """
        # Validate object type
        valid_types = ["person", "company", "deal", "user"]
        if lead_data.object_type not in valid_types:
            raise AttioAPIError(f"Invalid object_type: {lead_data.object_type}. Must be one of {valid_types}")

        # Convert lead data to dictionary
        data = self._lead_data_to_dict(lead_data)

        # If creating a person with a company, create the company first
        company_record = None
        company_domain = None
        if lead_data.object_type == "person" and data.get('company'):
            logger.info(f"Creating company '{data['company']}' for person")
            # Extract company-specific notes from the overall notes
            company_notes = data.get('notes', '')  # Could extract company-specific info here
            company_record, company_domain = self._create_or_get_company(data['company'], company_notes)
            if company_record:
                # Prefer record_id first
                record_id = company_record.get('id', {}).get('record_id')
                if record_id:
                    data['company_record_id'] = record_id
                    logger.info(f"Will link person to company ID: {data['company_record_id']}")
                elif company_domain:
                    # Fallback to domain if no record_id
                    data['company_domain'] = company_domain
                    logger.info(f"Will link person to company domain: {data['company_domain']}")
            else:
                logger.warning(f"Failed to create company, will skip linking")

        # Build Attio payload based on object type
        payload = self._build_attio_payload(data, lead_data.object_type)

        # Determine endpoint
        object_plural = {
            "person": "people",
            "company": "companies",
            "deal": "deals",
            "user": "users"
        }
        object_slug = object_plural[lead_data.object_type]
        endpoint = f"{self.base_url}/objects/{object_slug}/records"

        try:
            logger.info(f"Creating {lead_data.object_type} in Attio: {lead_data.name}")

            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=15
            )

            response.raise_for_status()
            created_record = response.json()

            record_id = created_record.get('id', {}).get('record_id', 'unknown')
            logger.info(f"Successfully created {lead_data.object_type}: {record_id}")

            # Company link is already included in the creation payload if available
            # No separate linking step needed

            return created_record

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create {lead_data.object_type} in Attio: {e}")

            # Check if error is due to missing attribute
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', '')

                    # Check if it's a missing attribute error
                    if 'Cannot find attribute' in error_message:
                        # Extract attribute name from error message
                        # Format: "Cannot find attribute with slug/ID "attribute_name"."
                        import re
                        match = re.search(r'Cannot find attribute with slug/ID ["\'\u201c]([^"\'\u201d]+)["\'\u201d]', error_message)
                        if match:
                            missing_attribute = match.group(1)
                            logger.info(f"Attribute '{missing_attribute}' not found, creating it...")

                            try:
                                # Create the missing attribute
                                self._create_attribute(object_slug, missing_attribute)

                                # Retry the record creation
                                logger.info(f"Retrying record creation after creating attribute '{missing_attribute}'")
                                response = requests.post(
                                    endpoint,
                                    headers=self.headers,
                                    json=payload,
                                    timeout=15
                                )
                                response.raise_for_status()
                                created_record = response.json()

                                record_id = created_record.get('id', {}).get('record_id', 'unknown')
                                logger.info(f"Successfully created {lead_data.object_type}: {record_id}")
                                return created_record
                            except Exception as create_error:
                                logger.error(f"Failed to create attribute '{missing_attribute}': {create_error}")
                                # Continue to raise the original error below
                        else:
                            logger.warning(f"Could not extract attribute name from error: {error_message}")
                except Exception as retry_error:
                    logger.error(f"Failed to auto-create attribute and retry: {retry_error}", exc_info=True)

            # If we couldn't handle it, extract error details and raise
            error_detail = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get('message', str(e))
                except:
                    pass

            raise AttioAPIError(f"{lead_data.object_type.capitalize()} creation failed: {error_detail}")

    def _link_person_to_company(self, person_record_id: str, company_domain: Optional[str] = None, company_record_id: Optional[str] = None) -> None:
        """
        Link a person to a company after both are created.

        Args:
            person_record_id: Record ID of the person
            company_domain: Domain of the company (preferred method)
            company_record_id: Record ID of the company (fallback)

        Raises:
            AttioAPIError: If linking fails
        """
        try:
            endpoint = f"{self.base_url}/objects/people/records/{person_record_id}"

            # Prefer linking by record_id first, fallback to domain
            if company_record_id:
                # Link by record_id - Attio reference format
                company_value = [{
                    'target_object': 'companies',
                    'target_record_id': company_record_id
                }]
                logger.info(f"Linking person {person_record_id} to company by ID: {company_record_id}")
            elif company_domain:
                # Link by domain - simpler format
                company_value = company_domain
                logger.info(f"Linking person {person_record_id} to company by domain: {company_domain}")
            else:
                logger.error("No company record_id or domain provided for linking")
                return

            # PATCH request to add the company relationship
            payload = {
                'data': {
                    'values': {
                        'companies': company_value
                    }
                }
            }

            logger.info(f"Link payload: {payload}")

            response = requests.patch(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=15
            )

            response.raise_for_status()
            logger.info(f"Successfully linked person to company")

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to link person to company: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    logger.error(f"Link error details: {error_data}")
                except:
                    pass
            # Don't raise - the person was created successfully, just without the link
            # We log the error but don't fail the whole operation

    def _create_or_get_company(self, company_name: str, notes: str = None) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Create a company record or get existing one.
        Searches for the company website using Gemini with web search.

        Args:
            company_name: Name of the company
            notes: Optional notes/description for the company

        Returns:
            Tuple of (company_record dictionary, domain string)

        Raises:
            AttioAPIError: If company creation fails
        """
        try:
            # Search for company website using Gemini
            website_domain = self._search_company_website(company_name)

            # Create company record with website
            company_values = {
                'name': company_name
            }

            if website_domain:
                company_values['domains'] = [{'domain': website_domain}]
                logger.info(f"Found and adding domain {website_domain} to company {company_name}")
            else:
                logger.info(f"No website found for company {company_name}, creating without domain")

            # Add company description/notes if provided
            if notes:
                company_values['description'] = notes
                logger.info(f"Adding description to company: {notes}")

            company_payload = {
                'data': {
                    'values': company_values
                }
            }

            endpoint = f"{self.base_url}/objects/companies/records"

            logger.info(f"Creating company: {company_name}")
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=company_payload,
                timeout=15
            )

            response.raise_for_status()
            company_record = response.json()

            # Log the full response to debug record_id extraction
            logger.info(f"Company creation response: {company_record}")
            logger.info(f"Successfully created company: {company_name}")
            return company_record, website_domain

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create company '{company_name}': {e}")
            # If creation fails, return None and we'll just skip the link
            return None, None

    def _is_quota_error(self, error: Exception) -> bool:
        """
        Check if an error is a quota/rate limit error.

        Args:
            error: Exception from Gemini API

        Returns:
            True if it's a quota error, False otherwise
        """
        error_str = str(error).lower()
        quota_indicators = [
            'quota',
            'rate limit',
            'resource exhausted',
            '429',
            'too many requests',
            'limit exceeded'
        ]
        return any(indicator in error_str for indicator in quota_indicators)

    def _search_company_website(self, company_name: str, use_fallback: bool = False) -> Optional[str]:
        """
        Search for a company's website using Gemini.
        Automatically falls back to lite model if quota is exceeded.

        Args:
            company_name: Name of the company
            use_fallback: If True, use the fallback model directly

        Returns:
            Company website domain or None if not found
        """
        # Choose model based on fallback flag
        model_name = Config.GOOGLE_FALLBACK_MODEL if use_fallback else Config.GOOGLE_MODEL

        try:
            logger.info(f"Searching for website of company: {company_name} using {model_name}")

            # Use Gemini to search for the company website
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 200,
                }
            )

            prompt = f"""Find the official website domain for the company "{company_name}".

Return ONLY the domain name (e.g., "example.com") without https:// or www.
If you cannot find a reliable website, return "NONE".

Examples:
- Input: "Stripe" -> Output: "stripe.com"
- Input: "Anthropic" -> Output: "anthropic.com"
- Input: "Unknown Fake Company XYZ" -> Output: "NONE"

Company: {company_name}
Website domain:"""

            response = model.generate_content(prompt)

            if response.text:
                website = response.text.strip().lower()

                # Remove common prefixes
                website = website.replace('https://', '').replace('http://', '')
                website = website.replace('www.', '')
                website = website.strip('/')

                # Check if it looks like a valid domain
                if website != "none" and '.' in website and ' ' not in website:
                    logger.info(f"Found website for {company_name}: {website}")
                    return website
                else:
                    logger.info(f"No valid website found for {company_name}")
                    return None

            return None

        except Exception as e:
            logger.error(f"Error searching for company website with {model_name}: {e}")

            # If primary model failed due to quota and we haven't tried fallback yet
            if not use_fallback and self._is_quota_error(e):
                logger.warning(f"Quota exceeded on {Config.GOOGLE_MODEL}, falling back to {Config.GOOGLE_FALLBACK_MODEL}")
                try:
                    return self._search_company_website(company_name, use_fallback=True)
                except Exception as fallback_error:
                    logger.error(f"Fallback model also failed: {fallback_error}")
                    return None

            return None

    def _create_attribute(self, object_slug: str, attribute_slug: str) -> None:
        """
        Create a new attribute in Attio for the specified object.

        Args:
            object_slug: The object type (people, companies, deals, users)
            attribute_slug: The attribute slug to create

        Raises:
            AttioAPIError: If attribute creation fails
        """
        # Map common attribute slugs to their proper types and titles
        attribute_config = {
            'linkedin_url': {
                'title': 'LinkedIn URL',
                'type': 'text',
                'is_multiselect': False
            },
            'job_title': {
                'title': 'Job Title',
                'type': 'text',
                'is_multiselect': False
            },
            'location': {
                'title': 'Location',
                'type': 'text',
                'is_multiselect': False
            },
            'description': {
                'title': 'Description',
                'type': 'text',
                'is_multiselect': False
            },
            'companies': {
                'title': 'Companies',
                'type': 'reference',  # Reference/relationship type
                'is_multiselect': True,  # Can link to multiple companies
                'reference_object': 'companies'  # Links to companies object
            },
        }

        # Get config for this attribute, or use defaults
        config = attribute_config.get(attribute_slug, {
            'title': attribute_slug.replace('_', ' ').title(),
            'type': 'text',
            'is_multiselect': False
        })

        # Build base payload
        attribute_data = {
            'title': config['title'],
            'api_slug': attribute_slug,
            'description': f"Auto-created attribute for {config['title']}",
            'type': config['type'],
            'is_multiselect': config['is_multiselect'],
            'is_required': False,
            'is_unique': False,
        }

        # Add config based on type
        if config['type'] == 'reference' and 'reference_object' in config:
            # For reference/relationship types, we need to specify the target object
            attribute_data['config'] = {
                'reference': {
                    'target_object': config['reference_object']
                }
            }
        else:
            attribute_data['config'] = {}

        payload = {'data': attribute_data}

        endpoint = f"{self.base_url}/objects/{object_slug}/attributes"

        try:
            logger.info(f"Creating attribute '{attribute_slug}' for {object_slug} with payload: {payload}")

            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=15
            )

            response.raise_for_status()
            logger.info(f"Successfully created attribute '{attribute_slug}'")

        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_detail = f"{e.response.status_code}: {error_data}"
                    logger.error(f"Attio API error creating attribute: {error_detail}")
                except:
                    logger.error(f"Failed to create attribute '{attribute_slug}': {e}")

            raise AttioAPIError(f"Attribute creation failed: {error_detail}")

    def _lead_data_to_dict(self, lead_data: LeadData) -> Dict[str, Any]:
        """
        Convert LeadData model to dictionary.

        Args:
            lead_data: Structured lead data from Gemini

        Returns:
            Dictionary with all available data
        """
        data = {
            'name': lead_data.name,
            'email': lead_data.email,
            'phone': lead_data.phone,
            'company': lead_data.company,
            'job_title': lead_data.job_title,
            'location': lead_data.location,
            'linkedin_url': lead_data.linkedin_url,
            'notes': lead_data.notes,
        }

        logger.info(f"Prepared data for: {data['name']}")
        return data

    def _build_attio_payload(self, data: Dict[str, Any], object_type: str) -> Dict[str, Any]:
        """
        Build Attio API payload based on object type.

        Args:
            data: Merged lead data
            object_type: Type of object (person, company, deal, user)

        Returns:
            Attio-formatted payload for the specific object type
        """
        if object_type == "person":
            return self._build_person_payload(data)
        elif object_type == "company":
            return self._build_company_payload(data)
        elif object_type == "deal":
            return self._build_deal_payload(data)
        elif object_type == "user":
            return self._build_user_payload(data)
        else:
            raise AttioAPIError(f"Unknown object type: {object_type}")

    def _build_person_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build payload for creating a person."""
        attributes = {
            'name': data.get('name'),
        }

        if data.get('email'):
            attributes['email_addresses'] = [{'email_address': data['email']}]

        if data.get('phone'):
            # Try simple structure first, fallback to just storing in notes if it fails
            attributes['phone_numbers'] = [{
                'original_phone_number': data['phone']
            }]

        if data.get('job_title'):
            attributes['job_title'] = data['job_title']

        if data.get('location'):
            attributes['location'] = data['location']

        if data.get('linkedin_url'):
            attributes['linkedin_url'] = data['linkedin_url']

        # Link to company in creation payload
        # Prefer domain string (simplest), fallback to record_id reference format
        if data.get('company_domain'):
            attributes['company'] = data['company_domain']
            logger.info(f"Adding company link by domain: {data['company_domain']}")
        elif data.get('company_record_id'):
            attributes['company'] = [{
                'target_object': 'companies',
                'target_record_id': data['company_record_id']
            }]
            logger.info(f"Adding company link by record_id: {data['company_record_id']}")

        # Build notes
        notes_parts = []
        if data.get('notes'):
            notes_parts.append(data['notes'])

        if notes_parts:
            attributes['description'] = "\n".join(notes_parts)

        return {'data': {'values': attributes}}

    def _build_company_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build payload for creating a company."""
        attributes = {
            'name': data.get('company') or data.get('name'),
        }

        if data.get('location'):
            attributes['locations'] = [data['location']]

        if data.get('email'):
            attributes['domains'] = [{'domain': data['email'].split('@')[1] if '@' in data['email'] else data['email']}]

        # Build description with any contact info
        desc_parts = []
        if data.get('name') and data.get('company'):
            desc_parts.append(f"Contact: {data['name']}")
        if data.get('job_title'):
            desc_parts.append(f"Title: {data['job_title']}")
        if data.get('email'):
            desc_parts.append(f"Email: {data['email']}")
        if data.get('phone'):
            desc_parts.append(f"Phone: {data['phone']}")
        if data.get('linkedin_url'):
            desc_parts.append(f"LinkedIn: {data['linkedin_url']}")
        if data.get('notes'):
            desc_parts.append(f"\n{data['notes']}")

        if desc_parts:
            attributes['description'] = "\n".join(desc_parts)

        return {'data': {'values': attributes}}

    def _build_deal_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build payload for creating a deal."""
        attributes = {
            'name': data.get('name'),
        }

        if data.get('deal_value'):
            attributes['value'] = {
                'currency': 'USD',
                'value': int(data['deal_value'])
            }

        if data.get('deal_stage'):
            attributes['stage'] = data['deal_stage']

        # Build description
        desc_parts = []
        if data.get('company'):
            desc_parts.append(f"Company: {data['company']}")
        if data.get('name') and not data.get('company'):
            desc_parts.append(f"Contact: {data['name']}")
        if data.get('notes'):
            desc_parts.append(data['notes'])

        if desc_parts:
            attributes['description'] = "\n".join(desc_parts)

        return {'data': {'values': attributes}}

    def _build_user_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build payload for creating a user."""
        attributes = {
            'name': data.get('name'),
        }

        if data.get('email'):
            attributes['email_address'] = data['email']

        if data.get('job_title'):
            attributes['job_title'] = data['job_title']

        if data.get('notes'):
            attributes['description'] = data['notes']

        return {'data': {'values': attributes}}


async def create_record(
    lead_data: LeadData
) -> Dict[str, Any]:
    """
    Convenience function to create a record in Attio.

    Automatically creates the correct type (person, company, deal, or user)
    based on lead_data.object_type.

    Args:
        lead_data: Structured lead data from Gemini (includes object_type)

    Returns:
        Created record information

    Raises:
        AttioAPIError: If creation fails
    """
    client = AttioClient()
    return client.create_record(lead_data)


# For testing
if __name__ == "__main__":
    import asyncio
    from gemini_processor import LeadData

    async def test_attio():
        """Test Attio record creation."""
        # Test person creation
        test_person = LeadData(
            object_type="person",
            name="John Doe",
            email="john.doe@example.com",
            phone="+1-555-123-4567",
            company="Example Corp",
            job_title="Software Engineer",
            location="San Francisco, CA",
            notes="Met at tech conference"
        )

        # Test company creation
        test_company = LeadData(
            object_type="company",
            name="Acme Corp",
            location="New York",
            notes="SaaS company"
        )

        # Test deal creation
        test_deal = LeadData(
            object_type="deal",
            name="Enterprise Deal with TechCo",
            company="TechCo",
            deal_value=50000,
            deal_stage="negotiation",
            notes="Q1 2024 target"
        )

        try:
            result = await create_record(test_person)
            print(f"\n{test_person.object_type.capitalize()} created successfully!")
            print(f"Record ID: {result.get('id', {}).get('record_id')}")

        except AttioAPIError as e:
            print(f"Failed to create record: {e}")

    asyncio.run(test_attio())
